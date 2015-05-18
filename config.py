# config.py
__author__ = 'tim.dilauro@gmail.com'

import logging
log = logging.getLogger(__name__)
log.debug("Module '%s' loading from '%s'", __name__, __file__)

# Default configuration
# todo: change rmap production endpoint to http://rmapdns.ddns.net/api after testing
CONFIG = {
	'application': {
		'name': 'RMap-Datacite-Harvester',
	    'version': '0.9.0',
	    'id': 'http://rmap-project.org/rmap/agent/RMap-Datacite-Harvester-0.9.0',
	    'xslt': {
		    'log_message_prefix': 'RMap-Transform',
	        'log_fatal_prefix': 'FATAL',
	        'log_error_prefix': 'ERROR',
	        'log_warning_prefix': 'WARNING',
	        'log_info_prefix': 'INFO',
	        'log_debug_prefix': 'DEBUG',
	    },
	},

	'rmap': {
		'rmap_instances' : {
			'test' : {
				'name': 'RMap API Test endpoint',
				'endpoint': 'http://rmapdns.ddns.net/apitest',
			    'auth': {
					'type': 'Basic',
			        'username': '',
			        'password': '',
				},
			},  # test
			'production': {
				'name': 'RMap API Production endpoint',
				'endpoint': 'http://rmapdns.ddns.net:8080/apitest',
			    'auth': {
					'type': 'Basic',
			        'username': '',
			        'password': '',
				},
			},  # production

		},  # rmap_instances
	    # object_paths are appended to an instances endpoint to
	    # reference objects of a certain type
	    'object_paths': {
		    'disco': '/discos/',
	        'event': '/events/',
	    },
		'link_relations': {
			'tombstone': 'http://rmap-project.org/rmap/terms/tombstone',
			'create': 'http://www.w3.org/ns/prov#wasGeneratedBy',
			'none': None
		},
	},

    'persistence': {
		'oai_store': {
			'class': 'ExistDB',
			'endpoint': 'http://localhost:8080/exist/rest',
			'auth': {
		        'username': 'admin',
		        'password': '',
			},
			'collection': 'oai_store',
		},
        'disco_store': {
			'class': 'ExistDB',
			'endpoint': 'http://localhost:8080/exist/rest',
			'auth': {
		        'username': '',
		        'password': '',
			},
			'collection': 'rmap_disco',
		},

        'harvest_monitor': {
	        'class': 'mysql',
            'auth': {
		        'username': '',
		        'password': '',
			},
        },
    },

	'schemas': {
		'oai_datacite': {
		    'name': 'oai_datacite',
		    'title': 'OAI DataCite',
		    'ns': 'http://schema.datacite.org/oai/oai-1.0/',
		    'xslt': 'transforms/oai_datacite-to-disco.xsl',
		},
	},

	'repositories' : {
	    'datacite': {
		    'url': 'http://oai.datacite.org/oai',
	        'method': 'oai-pmh',
	        'nickname': 'datacite',
	        'fullname': 'DataCite',
	        'supports_datacite_query_encoding': True,
	        'preferred_metadata_prefix': 'oai_datacite',
	        'metadata_prefixes': {
		        'oai_dc': {
		            'name': 'oai_dc',
		            'title': 'OAI Dublin Core',
		            'schema': 'http://www.openarchives.org/OAI/2.0/oai_dc/',
		        },
		        'oai_datacite': {
		            'name': 'oai_datacite',
		            'title': 'OAI DataCite',
		            'schema': 'http://schema.datacite.org/oai/oai-1.0/',
		        },
		        'datacite': {
		            'name':'datacite',
	                'title': 'DataCite Direct format',
		        },
	        },
	    },
	},  # harvesters
} # CONFIG

class Config(dict):
	def __init__(self, key=None, config=None):
		if config is None:
			config = CONFIG
		if key is not None:
			for k in key.split('.'):
				config = config[k]
		super(Config, self).__init__(config)

	def get(self, key, default=None, key_sep='.'):
		# todo: this next line doesn't seem quite right, but it works for now, so sticking with it
		config = dict(self)
		if key is not None:
			for k in key.split(key_sep):
				if not config.has_key(k):
					config = default
					break
				config = config[k]
		return Config(config=config) if isinstance(config, dict) else config

	def __getitem__(self, key):
		return self.get(key)


log.debug("Module '%s' loaded", __name__)
