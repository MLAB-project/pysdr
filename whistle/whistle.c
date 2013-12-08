#include <stdio.h>
#include <errno.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include <jack/jack.h>

jack_port_t *input_i, *input_q;
jack_port_t *output_i, *output_q;
jack_client_t *client;

float shift_up;
float shift_down;

void cmult(float *ai, float *aq, float bi, float bq)
{
	float ai_ = *ai;
	*ai = ai_ * bi - *aq * bq;
	*aq = ai_ * bq + *aq * bi;
}

void freq_shift(float *i, float *q, int n, float interval)
{
	int x;
	for (x = 0; x < n; x++) {
		float m = ((float) x) * 2 * M_PI / interval;
		cmult(i + x, q + x, sin(m), cos(m));
	}
}

float fir_c[50] = { -0.0000237041, -0.0000547117, -0.0000849869, -0.0000952846,
       -0.0000538829,  0.0000852238,  0.0003827879,  0.0009129652,
        0.0017598552,  0.0030118432,  0.0047539473,  0.007058677 ,
        0.0099761947,  0.013524792 ,  0.0176828105,  0.0223831196,
        0.0275111084,  0.0329068485,  0.0383716773,  0.0436789758,
        0.0485884288,  0.0528626188,  0.0562844783,  0.0586739559,
        0.0599022619,  0.0599022619,  0.0586739559,  0.0562844783,
        0.0528626188,  0.0485884288,  0.0436789758,  0.0383716773,
        0.0329068485,  0.0275111084,  0.0223831196,  0.0176828105,
        0.013524792 ,  0.0099761947,  0.007058677 ,  0.0047539473,
        0.0030118432,  0.0017598552,  0.0009129652,  0.0003827879,
        0.0000852238, -0.0000538829, -0.0000952846, -0.0000849869,
       -0.0000547117, -0.0000237041 };

float state_i[49];
float state_q[49];

void fir(float *c, float *s, float *in, float *out, int taps, int nframes)
{
	int i, x;

	for (i = 0; i < nframes; i++)
		out[i] = 0;

	for (i = taps - 1; i < nframes; i++)
		for (x = 0; x < taps; x++)
			out[i] += in[i - x] * c[x];

	for (i = 0; i < taps - 1; i++) {
		for (x = 0; x < i + 1; x++)
			out[i] += in[i - x] * c[x];
		for (x = i; x < taps - 1; x++)
			out[i] += s[x] * c[taps - 1 - x + i];
	}

	for (i = nframes - taps + 1, x = 0; i < nframes; i++, x++)
		s[x] = in[i];
}

float buffer_i[10000];
float buffer_q[10000];

int process(jack_nframes_t nframes, void *arg)
{
	jack_default_audio_sample_t *in_i, *in_q, *out_i, *out_q;

	in_i = jack_port_get_buffer(input_i, nframes);
	in_q = jack_port_get_buffer(input_q, nframes);
	out_i = jack_port_get_buffer(output_i, nframes);
	out_q = jack_port_get_buffer(output_q, nframes);

	jack_nframes_t i;
	for (i = 0; i < nframes; i++) {
		buffer_i[i] = in_i[i];
		buffer_q[i] = in_q[i];
	}

	freq_shift(buffer_i, buffer_q, nframes, shift_down);
	fir(fir_c, state_i, buffer_i, out_i, 50, nframes);
	fir(fir_c, state_q, buffer_q, out_q, 50, nframes);
	freq_shift(out_i, out_q, nframes, shift_up);

	for (i = 0; i < nframes; i++) {
		out_i[i] = out_i[i] * 500;
		out_q[i] = out_q[i] * 500;
	}

	return 0;
}

void jack_shutdown(void *arg)
{
	exit(1);
}

int main(int argc, char *argv[])
{
	const char *client_name = "whistle";
	const char *server_name = NULL;
	jack_options_t options = JackNullOption;
	jack_status_t status;

	client = jack_client_open(client_name, options, &status, server_name);
	if (client == NULL) {
		fprintf(stderr, "jack_client_open() failed, "
			 "status = 0x%2.0x\n", status);
		if (status & JackServerFailed) {
			fprintf(stderr, "Unable to connect to JACK server\n");
		}
		exit(1);
	}
	if (status & JackServerStarted) {
		fprintf(stderr, "JACK server started\n");
	}
	if (status & JackNameNotUnique) {
		client_name = jack_get_client_name(client);
		fprintf(stderr, "unique name `%s' assigned\n", client_name);
	}

	jack_set_process_callback(client, process, 0);
	jack_on_shutdown(client, jack_shutdown, 0);

	printf("engine sample rate: %" PRIu32 "\n",
		jack_get_sample_rate (client));

	int i;
	for (i = 0; i < 49; i++)
		state_i[i] = state_q[i] = 0;

	float smp_rate = jack_get_sample_rate(client);

	shift_down = smp_rate / 10000;
	shift_up = -smp_rate / 1000;

	input_i = jack_port_register (client, "input_i",
					 JACK_DEFAULT_AUDIO_TYPE,
					 JackPortIsInput, 0);
	input_q = jack_port_register (client, "input_q",
					 JACK_DEFAULT_AUDIO_TYPE,
					 JackPortIsInput, 0);
	output_i = jack_port_register (client, "output_i",
					  JACK_DEFAULT_AUDIO_TYPE,
					  JackPortIsOutput, 0);
	output_q = jack_port_register (client, "output_q",
					  JACK_DEFAULT_AUDIO_TYPE,
					  JackPortIsOutput, 0);

	if (!input_i || !input_q || !output_i || !output_q) {
		fprintf(stderr, "no more JACK ports available\n");
		exit(1);
	}

	if (jack_activate(client)) {
		fprintf(stderr, "cannot activate client");
		exit(1);
	}

	sleep(-1);

	jack_client_close(client);
	exit(0);
}
