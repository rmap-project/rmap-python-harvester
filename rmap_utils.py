__author__ = 'timmo'

import logging
log = logging.getLogger(__name__)
log.debug("Module '%s' loading from '%s'", __name__, __file__)


def print_count(count=None, unit="unit"):
	pass

	"""
	import sys

	if count is None:
		sys.stdout.write('\n\r')
	else:
		sys.stdout.write('%s: %i\r' % (unit, count) )
	sys.stdout.flush()
	"""


def isodatez(date=None):
	from datetime import datetime
	if date is None:
		date = datetime.utcnow()
	return date.strftime('%Y-%m-%dT%H:%M:%S')+'Z'


log.debug("Module '%s' loaded", __name__)