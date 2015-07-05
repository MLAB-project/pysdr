import json

tuple2f = lambda x: (float(x[0]), float(x[1]))

fields = [
	(float, 'view.scale_x'),
	(float, 'view.scale_y'),
	(float, 'view.origin_x'),
	(float, 'view.origin_y'),
	(tuple2f, 'mag_range')
]

def getnestedattr(obj, name):
	if name == '':
		return obj

	for x in name.split('.'):
		obj = getattr(obj, x)

	return obj

def setnestedattr(obj, name, val):
	split = name.split('.')
	setattr(getnestedattr(obj, '.'.join(split[0:-1])), split[-1], val)

def pers_load(viewer, filename):
	try:
		obj = json.load(file(filename))
		for t, n in fields:
			setnestedattr(viewer, n, t(obj[n]))
	except IOError as e:
		print "could not load the persistance file:", e

def pers_save(viewer, filename):
	obj = dict([(name, getnestedattr(viewer, name)) for _, name in fields])
	fp = file(filename, 'w')
	json.dump(obj, fp, indent=4)
	fp.write('\n')
	fp.close()
