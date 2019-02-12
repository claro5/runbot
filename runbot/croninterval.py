# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
import logging

import odoo
from .models.repo import CronHostError

# increase cron frequency from 0.016 Hz to 0.1 Hz to reduce starvation and improve throughput with many workers
# TODO: find a nicer way than monkey patch to accomplish this
odoo.service.server.SLEEP_INTERVAL = 10
odoo.addons.base.ir.ir_cron._intervalTypes['minutes'] = lambda interval: relativedelta(seconds=interval * 10)

_logger = logging.getLogger(__name__)


def no_log_CronHostError(record):
    if record.exc_info and record.exc_info[0] is CronHostError:
        return False
    return True


logging.getLogger('odoo.addons.base.ir.ir_cron').addFilter(no_log_CronHostError)
