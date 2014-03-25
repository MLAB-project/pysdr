#define _GNU_SOURCE

#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dlfcn.h>
#include <alloca.h>
#include <complex.h>

#include <sys/sendfile.h>  // sendfile
#include <fcntl.h>         // open
#include <unistd.h>        // close
#include <sys/stat.h>      // fstat
#include <sys/types.h>     // fstat
#include <sys/inotify.h>
#include <libgen.h>

#include <jack/jack.h>

#include "whistle.h"

typedef stage_t *(*stage_const_t)(float samp_rate, int nargs, char *args);

stage_t *create_stage(float samp_rate, char *desc)
{
	int nargs = 1;

	int i;
	for (i = 0; desc[i]; i++) {
		if (desc[i] == ',') {
			nargs++;
			desc[i] = '\0';
		}
	}

	stage_const_t cons = (stage_const_t) dlsym(RTLD_DEFAULT, desc);

	if (!cons) {
		fprintf(stderr, "whistle: '%s': no such stage constructor\n", desc);
		return NULL;
	}

	return cons(samp_rate, nargs - 1, desc + strlen(desc) + 1);
}

pipeline_t *pipeline_create(float samp_rate, unsigned int buffer_size,
							char *desc)
{
	int i;

	pipeline_t *pipeline = (pipeline_t *) malloc(sizeof(pipeline_t));

	if (!pipeline)
		return NULL;

	pipeline->buffer_size = buffer_size;
	pipeline->nstages = 1;
	pipeline->input_buffers = NULL;
	pipeline->stages = NULL;

	pipeline->desc = (char *) malloc(strlen(desc) + 1);
	strcpy(pipeline->desc, desc);
	desc = pipeline->desc;

	for (i = 0; desc[i]; i++) {
		if (desc[i] == ':') {
			pipeline->nstages++;
			desc[i] = '\0';
		}
	}

	pipeline->stages = (stage_t **) malloc(sizeof(stage_t *) * pipeline->nstages);

	if (!pipeline->stages)
		goto cleanup;

	memset(pipeline->stages, 0, sizeof(stage_t *) * pipeline->nstages);

	for (i = 0; i < pipeline->nstages; i++) {
		char *next = desc + strlen(desc) + 1;
		pipeline->stages[i] = create_stage(samp_rate, desc);

		if (!pipeline->stages[i])
			goto cleanup;

		desc = next;
	}

	pipeline->input_buffers = (float **) malloc(sizeof(float *) * pipeline->nstages);

	if (!pipeline->input_buffers)
		goto cleanup;

	for (i = 0; i < pipeline->nstages; i++) {
		size_t bsize = sizeof(float *) * 2 * (buffer_size + pipeline->stages[i]->prelude);
		pipeline->input_buffers[i] = (float *) malloc(bsize);

		if (!pipeline->input_buffers[i])
			goto cleanup;
	}

	return pipeline;

cleanup:
	pipeline_delete(pipeline);

	return NULL;
}

void pipeline_delete(pipeline_t *pipeline)
{
	int i;

	if (pipeline->desc)
		free(pipeline->desc);

	if (pipeline->input_buffers) {
		for (i = 0; i < pipeline->nstages; i++)
			if (pipeline->input_buffers[i])
				free(pipeline->input_buffers[i]);

		free(pipeline->input_buffers);
	}

	if (pipeline->stages) {
		for (i = 0; i < pipeline->nstages; i++)
			if (pipeline->stages[i])
				pipeline->stages[i]->free(pipeline->stages[i]);

		free(pipeline->stages);
	}

	free(pipeline);
}

float *pipeline_input_buffer(pipeline_t *pipeline)
{
	return pipeline->input_buffers[0] + 2 * pipeline->stages[0]->prelude;
}

void pipeline_pass(pipeline_t *pipeline, float *out, unsigned int nframes)
{
	if (nframes > pipeline->buffer_size) {
		fprintf(stderr, "whistle: pipeline_pass: nframes > buffer_size\n");
		exit(1);
	}

	float *s_in = pipeline_input_buffer(pipeline);

	int i;
	for (i = 0; i < pipeline->nstages; i++) {
		float *s_out;

		if (i < pipeline->nstages - 1)
			s_out = pipeline->input_buffers[i + 1] + 2 * pipeline->stages[i + 1]->prelude;
		else
			s_out = out;

		pipeline->stages[i]->pass(pipeline->stages[i], s_in, s_out, nframes);

		int x;
		for (x = -pipeline->stages[i]->prelude * 2; x < 0; x++)
			*(s_in + x) = *(s_in + x + 2 * nframes);

		s_in = s_out;
	}
}

void dummy_free(stage_t *stage)
{
	free(stage);
}

typedef struct {
	stage_t stage;
	unsigned int order;
	float *c;
} fir_stage_t;

void fir_free(stage_t *stage)
{
	free(((fir_stage_t *) stage)->c);
	free(stage);
}

void fir_stride_pass(float *c, float *in, float *out, unsigned int nframes, unsigned int order)
{
	int i, x;
	for (i = 0; i < nframes; i++) {
		float sum = 0;
		for (x = 0; x < order; x++)
			sum += c[x] * *(in + 2 * (i - x));
		out[2 * i] = sum;
	}
}

void fir_pass(stage_t *stage, float *in, float *out, unsigned int nframes)
{
	fir_stage_t *fir = (fir_stage_t *) stage;
	fir_stride_pass(fir->c, in, out, nframes, fir->order);
	fir_stride_pass(fir->c, in + 1, out + 1, nframes, fir->order);
}

// ported from http://www.arc.id.au/dspUtils-10.js
double kb_ino(double x)
{
	double d = 0, ds = 1, s = 1;

	do {
		d += 2;
		ds *= x*x / (d*d);
		s += ds;
	} while (ds > s * 0.000001);

	return s;
}

void kaiser_bessel(float fs, float fa, float fb,
					int m, float att, float *h)
{
	int np = (m - 1) / 2;
	double *a = (double *) alloca(sizeof(double) * (np + 1));
	int i;

	a[0] = 2 * (fb - fa) / fs;

	for (i = 1; i <= np; i++)
		a[i] = (sin(2.0f * i * M_PI * (fb / fs)) - sin(2.0f * i * M_PI * (fa / fs))) / (i * M_PI);

	double alpha;

	if (att < 21)
		alpha = 0;
	else if (att > 50)
		alpha = 0.1102 * (att - 8.7);
	else
		alpha = 0.5842 * pow(att - 21, 0.4) + 0.07886 * (att - 21);

	double inoalpha = kb_ino(alpha);

	for (i = 0; i <= np; i++)
		h[np + i] = a[i] * kb_ino(alpha * sqrt(1.0 - ((double) (i * i)) / (np * np))) / inoalpha;

	for (i = 0; i < np; i++)
		h[i] = h[m - 1 - i];
}

stage_t *kbfir(float samp_rate, int nargs, char *args)
{
	if (nargs != 4)
		goto usage;

	int ntaps = atoi(args);
	args += strlen(args) + 1;

	if (!(ntaps > 0 && ntaps % 2))
		goto usage;

	float fa = atof(args);
	args += strlen(args) + 1;
	float fb = atof(args);
	args += strlen(args) + 1;
	float att = atof(args);

	fir_stage_t *fir = (fir_stage_t *) malloc(sizeof(fir_stage_t));

	if (!fir)
		return NULL;

	float *c = (float *) malloc(sizeof(float) * ntaps);

	if (!c) {
		free(fir);
		return NULL;
	}

	kaiser_bessel(samp_rate, fa, fb, ntaps, att, c);

	fir->stage.pass = fir_pass;
	fir->stage.free = fir_free;
	fir->stage.prelude = ntaps - 1;
	fir->order = ntaps;
	fir->c = c;

	return (stage_t *) fir;

usage:
	fprintf(stderr, "kbfir: usage: kbfir,NTAPS,FA,FB,ATT\n");
	fprintf(stderr, "kbfir: NTAPS must be an positive odd number\n");
	return NULL;
}

stage_t *customfir(float samp_rate, int nargs, char *args)
{
	fir_stage_t *fir = (fir_stage_t *) malloc(sizeof(fir_stage_t));

	if (!fir)
		return NULL;

	float *c = (float *) malloc(sizeof(float) * nargs);

	if (!c) {
		free(fir);
		return NULL;
	}

	int i;
	for (i = 0; i < nargs; i++) {
		c[i] = atof(args);
		args += strlen(args) + 1;
	}

	fir->stage.pass = fir_pass;
	fir->stage.free = fir_free;
	fir->stage.prelude = nargs - 1;
	fir->order = nargs;
	fir->c = c;

	return (stage_t *) fir;
}

void fmdemod_pass(stage_t *stage, float *in, float *out, unsigned int nframes)
{
	int i;
	for (i = 0; i < nframes * 2; i += 2) {
		float di = in[i] - in[i - 4];
		float dq = in[i + 1] - in[i - 3];

		float m = in[i - 2] * in[i - 2] + in[i - 1] * in[i - 1];
		out[i] = (in[i - 2] * dq - in[i - 1] * di) / m;

		out[i + 1] = 0;
	}
}

stage_t *fmdemod(float samp_rate, int nargs, char *args)
{
	if (nargs != 0) {
		fprintf(stderr, "fmdemod: usage: fmdemod\n");
		return NULL;
	}

	stage_t *stage = (stage_t *) malloc(sizeof(stage_t));

	if (!stage)
		return NULL;

	stage->pass = fmdemod_pass;
	stage->free = dummy_free;
	stage->prelude = 2;

	return stage;
}

typedef struct {
	stage_t stage;
	float complex inc;
	float complex phase;
} freqx_stage_t;

void freqx_pass(freqx_stage_t *fs, float complex *in, float complex *out, unsigned int nframes)
{
	float complex inc = fs->inc;
	float complex phase = fs->phase;

	int x;
	for (x = 0; x < nframes; x++) {
		out[x] = in[x] * phase;
		phase *= inc;
	}

	fs->phase = phase / cabs(phase);
}

stage_t *freqx(float samp_rate, int nargs, char *args)
{
	if (nargs != 1) {
		fprintf(stderr, "freqx: usage: freqx,FREQ\n");
		return NULL;
	}

	freqx_stage_t *fs = (freqx_stage_t *) malloc(sizeof(freqx_stage_t));

	if (!fs)
		return NULL;

	fs->stage.pass = (stage_pass_cb_t) freqx_pass;
	fs->stage.free = dummy_free;
	fs->stage.prelude = 0;
	fs->phase = 1;
	fs->inc = cexp(I * (atof(args) / samp_rate) * 2 * M_PI);

	return (stage_t *) fs;
}

typedef struct {
	stage_t stage;
	float factor;
} amplify_stage_t;

void amplify_pass(stage_t *stage, float *in, float *out, unsigned int nframes)
{
	float factor = ((amplify_stage_t *) stage)->factor;

	int i;
	for (i = 0; i < nframes * 2; i++)
		out[i] = in[i] * factor;
}

stage_t *amplify(float samp_rate, int nargs, char *args)
{
	if (nargs != 1) {
		fprintf(stderr, "amplify: usage: amplify,FACTOR\n");
		return NULL;
	}

	amplify_stage_t *amp = (amplify_stage_t *) malloc(sizeof(amplify_stage_t));

	if (!amp)
		return NULL;

	amp->stage.pass = (stage_pass_cb_t) amplify_pass;
	amp->stage.free = dummy_free;
	amp->stage.prelude = 0;
	amp->factor = atof(args);

	return (stage_t *) amp;
}

typedef struct {
	stage_t stage;
	char *lib_path;
	char *lib_copy_path;
	void *dl_handle;
	int inotify_handle;
	stage_t *lib_stage;
	int nargs;
	char *args;
	float samp_rate;
} dl_stage_t;

char copy_file(char *source, char *dest)
{
	int fd_source = open(source, O_RDONLY, 0);
	int fd_dest = open(dest, O_WRONLY | O_CREAT | O_TRUNC, S_IRWXU);

	struct stat stat_source;
	fstat(fd_source, &stat_source);
	sendfile(fd_dest, fd_source, 0, stat_source.st_size);

	close(fd_source);
	close(fd_dest);

	return 1;
}

char dl_load(dl_stage_t *stage)
{
	stage->lib_copy_path = tempnam(NULL, "whistle_dl_copy_");

	if (!stage->lib_copy_path) {
		perror("whistle: tempnam");
		return 0;
	}

	fprintf(stderr, "dl: copy of %s will be at %s\n", stage->lib_path, stage->lib_copy_path);

	copy_file(stage->lib_path, stage->lib_copy_path);

	stage->dl_handle = dlopen(stage->lib_copy_path, RTLD_NOW);

	if (!stage->dl_handle) {
		perror("whistle: dlopen");
		return 0;
	}

	char *sym = stage->args + strlen(stage->args) + 1;

	stage_const_t cons = (stage_const_t) dlsym(stage->dl_handle, sym);

	if (!cons) {
		fprintf(stderr, "whistle: %s: '%s': no such stage constructor\n",
				stage->lib_path, sym);
		return 0;
	}

	stage->lib_stage = cons(stage->samp_rate, stage->nargs - 2, sym + strlen(sym) + 1);

	if (!cons)
		return 0;

	return 1;
}

void dl_unload(dl_stage_t *stage)
{
	if (stage->lib_copy_path)
		free(stage->lib_copy_path);

	if (stage->lib_stage)
		stage->lib_stage->free(stage->lib_stage);

	if (stage->dl_handle)
		dlclose(stage->dl_handle);

	stage->lib_copy_path = NULL;
	stage->lib_stage = NULL;
	stage->dl_handle = NULL;
}

void dl_pass_proxy(dl_stage_t *stage, float *in, float *out, int nframes)
{
	fd_set sready;
	struct timeval nowait;

	FD_ZERO(&sready);
	FD_SET((unsigned int) stage->inotify_handle, &sready);
	memset((char *) &nowait, 0, sizeof(nowait));

	select(stage->inotify_handle + 1, &sready, NULL, NULL, &nowait);

	if (FD_ISSET(stage->inotify_handle, &sready)) {
		char buffer[4096];
		int ret = read(stage->inotify_handle, buffer, sizeof(buffer));

		int i = 0;
		while (i < ret) {
			struct inotify_event *event = (struct inotify_event *) &buffer[i];

			if (!strcmp(event->name, basename(stage->lib_path))) {
				dl_unload(stage);
				if (!dl_load(stage)) {
					fprintf(stderr, "whistle: dl hotswap failed\n");
					exit(1);
				}
			}

			i += sizeof(struct inotify_event) + event->len;
		}
	}

	stage->lib_stage->pass(stage->lib_stage, in, out, nframes);
}

void dl_stage_free(dl_stage_t *stage)
{
	dl_unload(stage);

	if (stage->lib_path)
		free(stage->lib_path);

	if (stage->inotify_handle >= 0)
		close(stage->inotify_handle);

	free(stage);
}

stage_t *dl(float samp_rate, int nargs, char *args)
{
	if (nargs < 2) {
		fprintf(stderr, "dl: usage: dl,LIB_PATH,CONSTRUCTOR_SYM\n");
		return NULL;
	}

	dl_stage_t *dl_stage = (dl_stage_t *) malloc(sizeof(dl_stage_t));

	if (!dl_stage)
		return NULL;

	dl_stage->samp_rate = samp_rate;
	dl_stage->lib_copy_path = NULL;
	dl_stage->dl_handle = NULL;
	dl_stage->inotify_handle = -1;
	dl_stage->lib_stage = NULL;
	dl_stage->lib_path = NULL;

	dl_stage->nargs = nargs;
	dl_stage->args = args;

	dl_stage->lib_path = malloc(strlen(args) + 1);

	if (!dl_stage->lib_path)
		goto cleanup;

	strcpy(dl_stage->lib_path, args);

	dl_stage->inotify_handle = inotify_init();
	if (inotify_add_watch(dl_stage->inotify_handle, dirname(dl_stage->lib_path),
							IN_CLOSE_WRITE | IN_MOVED_TO) < 0)
		perror("whistle: inotify_add_watch");

	strcpy(dl_stage->lib_path, args);

	if (!dl_load(dl_stage))
		goto cleanup;

	dl_stage->stage.prelude = dl_stage->lib_stage->prelude;
	dl_stage->stage.pass = (stage_pass_cb_t) dl_pass_proxy;
	dl_stage->stage.free = (stage_free_cb_t) dl_stage_free;

	return (stage_t *) dl_stage;

cleanup:
	if (dl_stage)
		dl_stage_free(dl_stage);

	return NULL;
}

typedef struct {
	char *pipeline_desc;
	pipeline_t *pipeline;
	jack_port_t *p_in_i, *p_in_q, *p_out_i, *p_out_q;
	float *output_buffer;
	jack_nframes_t sample_rate;
	jack_nframes_t buffer_size;
} jack_arg_t;

int jack_process(jack_nframes_t nframes, void *arg_)
{
	jack_arg_t *arg = (jack_arg_t *) arg_;
	pipeline_t *pipeline = arg->pipeline;

	jack_default_audio_sample_t *in_i, *in_q, *out_i, *out_q;

	in_i = jack_port_get_buffer(arg->p_in_i, nframes);
	in_q = jack_port_get_buffer(arg->p_in_q, nframes);
	out_i = jack_port_get_buffer(arg->p_out_i, nframes);
	out_q = jack_port_get_buffer(arg->p_out_q, nframes);

	float *pl_in = pipeline_input_buffer(pipeline);
	float *pl_out = arg->output_buffer;

	int i;
	for (i = 0; i < nframes; i++) {
		pl_in[2 * i] = in_i[i];
		pl_in[2 * i + 1] = in_q[i];
	}

	pipeline_pass(pipeline, pl_out, nframes);

	for (i = 0; i < nframes; i++) {
		out_i[i] = pl_out[2 * i];
		out_q[i] = pl_out[2 * i + 1];
	}
}

void jack_shutdown(void *arg)
{
	exit(1);
}

int jack_setup_pipeline(jack_arg_t *arg)
{
	if (arg->buffer_size && arg->sample_rate) {
		if (arg->pipeline)
			pipeline_delete(arg->pipeline);

		if (arg->output_buffer)
			free(arg->output_buffer);

		arg->pipeline = pipeline_create(arg->sample_rate, arg->buffer_size, arg->pipeline_desc);
		arg->output_buffer = (float *) malloc(sizeof(float) * 2 * arg->buffer_size);

		return (arg->pipeline && arg->output_buffer) ? 0 : -1;
	}
}

int jack_buffer_size(jack_nframes_t nframes, void *arg_)
{
	jack_arg_t *arg = (jack_arg_t *) arg_;

	if (arg->buffer_size != nframes) {
		arg->buffer_size = nframes;
		return jack_setup_pipeline(arg);
	}

	return 0;
}

int jack_sample_rate(jack_nframes_t nframes, void *arg_)
{
	jack_arg_t *arg = (jack_arg_t *) arg_;

	if (arg->sample_rate != nframes) {
		arg->sample_rate = nframes;
		return jack_setup_pipeline(arg);
	}

	return 0;
}

#define BUFFER_SIZE 8192

void usage(char *argv0)
{
	fprintf(stderr, "%s: usage: %s [-r SAMPLE_RATE | -j JACK_CLIENT_NAME]"
			" [-p PIPELINE]\n", argv0, argv0);
	exit(1);
}

int main(int argc, char *argv[])
{
	float smp_rate = 0;
	enum { PIPE, JACK } mode = JACK;
	const char *client_name = "whistle";
	char *pipeline_desc = "freqx,-10000:kbfir,41,0,1000,100:freqx,1000:amplify,100";
	pipeline_t *pipeline;

	int c;
	while ((c = getopt(argc, argv, "hr:j:p:b")) >= 0) {
		switch (c) {
			case '?':
			case 'h':
				usage(argv[0]);

			case 'r':
				mode = PIPE;
				smp_rate = atof(optarg);
				if (smp_rate <= 0) {
					fprintf(stderr, "%s: %s: invalid sample rate\n", argv[0], optarg);
					exit(1);
				}
				break;

			case 'j':
				mode = JACK;
				client_name = optarg;
				break;

			case 'p':
				pipeline_desc = optarg;
				break;

			default:
				fprintf(stderr, "%d\n", c);
				abort();
		}
	}

	if (optind < argc || (mode == PIPE && smp_rate == 0))
		usage(argv[0]);

	if (mode == JACK) {
		jack_options_t options = JackNullOption;
		jack_status_t status;
		jack_client_t *client;

		client = jack_client_open(client_name, options, &status, NULL);

		if (!client) {
			fprintf(stderr, "whistle: jack_client_open(): failed, status = 0x%X\n", status);
			if (status & JackServerFailed)
				fprintf(stderr, "whistle: unable to connect to JACK server\n");
			return 1;
		}

		jack_arg_t arg;

		arg.pipeline_desc = pipeline_desc;

		arg.buffer_size = 0;
		arg.sample_rate = 0;
		arg.pipeline = 0;
		arg.output_buffer = 0;

		jack_set_process_callback(client, jack_process, &arg);
		jack_on_shutdown(client, jack_shutdown, &arg);
		jack_set_buffer_size_callback(client, jack_buffer_size, &arg);
		jack_set_sample_rate_callback(client, jack_sample_rate, &arg);

		arg.buffer_size = jack_get_buffer_size(client);
		arg.sample_rate = jack_get_sample_rate(client);

		if (jack_setup_pipeline(&arg))
			return 1;

		arg.p_in_i = jack_port_register(client, "input_i", JACK_DEFAULT_AUDIO_TYPE,
											JackPortIsInput, 0);
		arg.p_in_q = jack_port_register(client, "input_q", JACK_DEFAULT_AUDIO_TYPE,
											JackPortIsInput, 0);
		arg.p_out_i = jack_port_register(client, "output_i", JACK_DEFAULT_AUDIO_TYPE,
											JackPortIsOutput, 0);
		arg.p_out_q = jack_port_register(client, "output_q", JACK_DEFAULT_AUDIO_TYPE,
											JackPortIsOutput, 0);

		if (!(arg.p_in_i && arg.p_in_q && arg.p_out_i && arg.p_out_q)) {
			fprintf(stderr, "whistle: no more JACK ports available\n");
			return 1;
		}

		if (jack_activate(client)) {
			fprintf(stderr, "whistle: cannot activate JACK client\n");
			return 1;
		}

		sleep(-1);
	} else {
		pipeline = pipeline_create(smp_rate, BUFFER_SIZE, pipeline_desc);

		if (!pipeline)
			return 1;

		float buffer[BUFFER_SIZE * 2];
		int ret, len;

		while (1) {
			len = fread(pipeline_input_buffer(pipeline),
						sizeof(float) * 2, BUFFER_SIZE, stdin);

			if (len == 0) {
				if (ret = ferror(stdin)) {
					fprintf(stderr, "%s: fread: %s\n", argv[0], strerror(ret));
					exit(1);
				} else {
					exit(0);
				}
			}

			pipeline_pass(pipeline, buffer, len);

			ret = fwrite(buffer, sizeof(float) * 2, len, stdout);

			if (ret != len) {
				fprintf(stderr, "%s: fwrite: %s\n", argv[0], strerror(ferror(stdout)));
				exit(1);
			}
		}
	}

	exit(0);
}
