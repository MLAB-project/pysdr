#include "Python.h"
#include "math.h"
#include "numpy/ndarraytypes.h"
#include "numpy/ufuncobject.h"
#include "numpy/halffloat.h"

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
        {NULL, NULL, 0, NULL}
};

#if PY_VERSION_HEX >= 0x03000000
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,
    "pysdrext",
    NULL,
    -1,
    pysdrextMethods,
    NULL,
    NULL,
    NULL,
    NULL
};

PyMODINIT_FUNC PyInit_pysdrext(void)
{
    PyObject *m, *mag2col, *d;
    m = PyModule_Create(&moduledef);
    if (!m) {
        return NULL;
    }

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
PyMODINIT_FUNC initpysdrext(void)
{
    PyObject *m, *mag2col, *d;


    m = Py_InitModule("pysdrext", pysdrextMethods);
    if (m == NULL) {
        return;
    }

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