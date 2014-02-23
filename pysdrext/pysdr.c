#include "Python.h"
#include "math.h"
#include "numpy/ndarraytypes.h"
#include "numpy/ufuncobject.h"
#include "numpy/halffloat.h"
#include <jack/jack.h>
#include <jack/ringbuffer.h>

typedef struct {
    jack_client_t *client;
    jack_port_t *port_i, *port_q;
    jack_ringbuffer_t *ringbuffer;
    int overrun;
} jack_handle_t;

void pysdr_jack_handle_destructor(PyObject *object)
{
    jack_handle_t *handle = (jack_handle_t *) PyCapsule_GetPointer(object, NULL);

    jack_client_close(handle->client);
    free(handle);
}

int pysdr_jack_process(jack_nframes_t nframes, void *arg)
{
    jack_handle_t *handle = (jack_handle_t *) arg;

    float* i = (float *) jack_port_get_buffer(handle->port_i, nframes);
    float* q = (float *) jack_port_get_buffer(handle->port_q, nframes);

    int x;
    for (x = 0; x < nframes; x++) {
        if (jack_ringbuffer_write(handle->ringbuffer, (const char *) &(i[x]),
                                    sizeof(float)) < sizeof(float))
            handle->overrun++;
        if (jack_ringbuffer_write(handle->ringbuffer, (const char *) &(q[x]),
                                    sizeof(float)) < sizeof(float))
            handle->overrun++;
    }

    return 0;
}

static PyObject *pysdr_jack_init(PyObject *self, PyObject *args)
{
    const char *name;

    if (!PyArg_ParseTuple(args, "s", &name))
        return NULL;

    jack_handle_t *handle = (jack_handle_t *) malloc(sizeof(jack_handle_t));

    if ((handle->client = jack_client_open(name, JackNoStartServer, 0)) == 0) {
        free(handle);
        PyErr_SetString(PyExc_RuntimeError, "cannot create jack client");
        return NULL;
    }

    jack_set_process_callback(handle->client, pysdr_jack_process, handle);

    handle->port_i = jack_port_register(handle->client, "input_i", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);
    handle->port_q = jack_port_register(handle->client, "input_q", JACK_DEFAULT_AUDIO_TYPE,
                                        JackPortIsInput, 0);

    int sample_rate = jack_get_sample_rate(handle->client);
    handle->ringbuffer = jack_ringbuffer_create(4 * sample_rate * 2 * sizeof(float));
    handle->overrun = 0;

    return PyCapsule_New((void *) handle, NULL, pysdr_jack_handle_destructor);
}

static PyObject *pysdr_jack_get_sample_rate(PyObject *self, PyObject *args)
{
    PyObject *handle_obj;

    if (!PyArg_ParseTuple(args, "O", &handle_obj))
        return NULL;

    jack_handle_t *handle;
    if ((handle = PyCapsule_GetPointer(handle_obj, NULL)) == 0)
        return NULL;

    return Py_BuildValue("i", jack_get_sample_rate(handle->client));
}

static PyObject *pysdr_jack_activate(PyObject *self, PyObject *args)
{
    PyObject *handle_obj;

    if (!PyArg_ParseTuple(args, "O", &handle_obj))
        return NULL;

    jack_handle_t *handle;
    if ((handle = PyCapsule_GetPointer(handle_obj, NULL)) == 0)
        return NULL;

    if (jack_activate(handle->client)) {
        PyErr_SetString(PyExc_RuntimeError, "cannot activate jack client");
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject *pysdr_jack_gather_samples(PyObject *self, PyObject *args)
{
    PyObject *handle_obj;
    unsigned int frames_no;

    if (!PyArg_ParseTuple(args, "OI", &handle_obj, &frames_no))
        return NULL;

    jack_handle_t *handle;
    if ((handle = PyCapsule_GetPointer(handle_obj, NULL)) == 0)
        return NULL;

    if (jack_ringbuffer_read_space(handle->ringbuffer) < frames_no * 2 * sizeof(float)) {
        Py_INCREF(Py_None);
        return Py_None;
    }
    
    float *samples = (float *) PyDataMem_NEW(sizeof(float) * 2 * frames_no);

    int read = 0;
    while (read < frames_no)
        read += jack_ringbuffer_read(handle->ringbuffer, (char *) &(samples[2 * read]),
                                        2 * sizeof(float) * (frames_no - read));

    npy_intp dims[1] = { frames_no };
    PyObject *array = PyArray_SimpleNewFromData(1, dims, NPY_COMPLEX64, samples);

    ((PyArrayObject *) array)->flags |= NPY_OWNDATA; 

    return array;
}

float interpolate(float val, float x0, float x1, float y0, float y1)
{
    return (val - x0) * (y1 - y0) / (x1 - x0) + y0;
}

float mag2col_base(float val)
{
    if (val <= -1)
        return 0;

    if (val <= -0.5)
        return interpolate(val, -1, -0.5, 0.0, 1.0); 

    if (val <= 0.5)
        return 1.0;

    if (val <= 1)
        return interpolate(val, 0.5, 1.0, 1.0, 0.0);
    
    return 0.0;
}

float mag2col_base2(float val)
{
    if (val <= 0)
        return 0;
    if (val >= 1)
        return 1;

    return val;
}

float mag2col_base2_blue(float val)
{
    if (val <= -2.75)
        return 0;

    if (val <= -1.75)
        return val + 2.75;

    if (val <= -0.75)
        return -(val + 0.75);

    if (val <= 0)
        return 0;

    if (val >= 1)
        return 1;

    return val;
}

static void mag2col(char **args, npy_intp *dimensions,
                        npy_intp* steps, void* data)
{
    npy_intp i;
    npy_intp n = dimensions[0];
    char *in = args[0], *out = args[1];
    npy_intp in_step = steps[0], out_step = steps[1];

    for (i = 0; i < n; i++) {
        float mag = *((float *) in);

        *((unsigned int *) out) = (((unsigned int) (mag2col_base2(mag + 1.0) * 255)) << 24)
            | (((unsigned int) (mag2col_base2(mag) * 255)) << 16)
            | (((unsigned int) (mag2col_base2_blue(mag - 1.0) * 255)) << 8)
            | 0xff;

        in += in_step;
        out += out_step;
    }
}

PyUFuncGenericFunction funcs[1] = {&mag2col};
static char types[2] = {NPY_FLOAT, NPY_UINT};
static void *data[1] = {NULL};

static PyMethodDef pysdrextMethods[] = {
        {"jack_init", pysdr_jack_init, METH_VARARGS, NULL},
        {"jack_get_sample_rate", pysdr_jack_get_sample_rate, METH_VARARGS, NULL},
        {"jack_activate", pysdr_jack_activate, METH_VARARGS, NULL},
        {"jack_gather_samples", pysdr_jack_gather_samples, METH_VARARGS, NULL},
        {NULL, NULL, 0, NULL}
};

#if PY_VERSION_HEX >= 0x03000000
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "ext",
    NULL,
    -1,
    pysdrextMethods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit_ext(void)
{
    PyObject *m, *mag2col, *d;

    m = PyModule_Create(&moduledef);

    if (!m)
        return;

    import_array();
    import_umath();

    mag2col = PyUFunc_FromFuncAndData(funcs, data, types, 1, 1, 1,
                                   PyUFunc_None, "mag2col",
                                    "", 0);

    d = PyModule_GetDict(m);

    PyDict_SetItemString(d, "mag2col", mag2col);
    Py_DECREF(mag2col);

    return m;
}
#else
PyMODINIT_FUNC initext(void)
{
    PyObject *m, *mag2col, *d;

    m = Py_InitModule("ext", pysdrextMethods);

    if (!m)
        return;

    import_array();
    import_umath();

    mag2col = PyUFunc_FromFuncAndData(funcs, data, types, 1, 1, 1,
                                    PyUFunc_None, "mag2col",
                                    "l", 0);

    d = PyModule_GetDict(m);

    PyDict_SetItemString(d, "mag2col", mag2col);
    Py_DECREF(mag2col);
}
#endif
