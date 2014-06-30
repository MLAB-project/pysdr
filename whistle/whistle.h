#ifndef __WHISTLE_H__
#define __WHISTLE_H__

typedef struct stage_struct {
	void (*pass)(struct stage_struct *stage, float *in, float *out, unsigned int nframes);
	void (*free)(struct stage_struct *stage);
	unsigned int prelude;
} stage_t;

typedef void (*stage_pass_cb_t)(stage_t *stage, float *in, float *out, unsigned int nframes);
typedef void (*stage_free_cb_t)(stage_t *stage);

typedef struct {
	char *desc;
	stage_t **stages;
	float **input_buffers;
	int nstages;
	unsigned int buffer_size;
} pipeline_t;

pipeline_t *pipeline_create(float samp_rate, unsigned int buffer_size,
							char *desc);
void pipeline_delete(pipeline_t *pipeline);

float *pipeline_input_buffer(pipeline_t *pipeline);
void pipeline_pass(pipeline_t *pipeline, float *out, unsigned int nframes);

#endif /* __WHISTLE_H__ */
