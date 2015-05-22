# config.py
__author__ = 'tim.dilauro@gmail.com'

import os
import logging
_logger = logging.getLogger(__name__)
_logger.debug("Module '%s' loading from '%s'", __name__, __file__)



#######################################################################
# Constants / Defaults
#######################################################################

#######################################################################
# Module parameters for more obvious access
#######################################################################
_default_config_variable_name = 'CONFIG'
_config_file_function_name = 'get_config'

#######################################################################
# Functions
#######################################################################

def get_config(key=None, config=None, default=None, file=None):
	pass

# todo: probably should do some exception handling in here to give user more clues
def _get_config_dict_from_file(path, key=_default_config_variable_name):
	# todo: should be implemented in a safer way (but restricted execution is deprecated)
	safe_ns = {_config_file_function_name: _get_config_dict_from_file}
	execfile(path, {}, safe_ns)
	config = safe_ns[key]
	return config

#######################################################################
# Classes
#######################################################################

class Config(dict):
	def __init__(self, key=None, config_dict=None, filename=None, key_sep='.'):
		if filename is not None:
			config_dict = _get_config_dict_from_file(filename)
		elif config_dict is None:
			config_dict = {}
		if key is not None:
			for k in key.split(key_sep):
				config_dict = config_dict[k]
		super(Config, self).__init__(config_dict)

	def get(self, key, default=None, key_sep='.'):
		# todo: this next line doesn't seem quite right, but it works for now, so sticking with it
		config = dict(self)
		if key is not None:
			for k in key.split(key_sep):
				if not config.has_key(k):
					config = default
					break
				config = config[k]
		return Config(config_dict=config) if isinstance(config, dict) else config

	def __getitem__(self, key):
		return self.get(key)

if __name__ == "__main__":
	CONFIG_FILE = 'config/default.cfg'

	cfg = Config(filename=CONFIG_FILE)
	c = cfg['rmap.rmap_instances']
	r = Config('rmap', filename=CONFIG_FILE)

	print '\n** Next test(s) should print "XXX"'
	print r.get('link_relations.xxx', 'XXX')

	print '\n** Next test(s) should print a URL/URI'
	print c.get('test.endpoint')
	print c.get('test:endpoint', key_sep=':')
	print c['test.endpoint']

	print '\n** Next test(s) should print "None"'
	print r.get('link_relations.none', 'XXX')
	print c.get('test.endpoint', key_sep=':')
	print c.get('test:endpoint')
	pass

#######################################################################
# Epilogue
#######################################################################
_logger.debug("Module '%s' loaded", __name__)
