__author__ = 'timmo'

import logging
_logger = logging.getLogger(__name__)
_logger.debug("Module '%s' loading from '%s'", __name__, __file__)

def isodatez(date=None):
	from datetime import datetime
	if date is None:
		date = datetime.utcnow()
	return date.strftime('%Y-%m-%dT%H:%M:%S')+'Z'


#######################################################################
# Epilogue
#######################################################################
_logger.debug("Module '%s' loaded", __name__)