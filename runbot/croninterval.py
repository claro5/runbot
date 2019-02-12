# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta
from datetime import datetime
import logging
import pytz

import odoo
from .models.repo import CronHostError

# increase cron frequency from 0.016 Hz to 0.1 Hz to reduce starvation and improve throughput with many workers
# TODO: find a nicer way than monkey patch to accomplish this
odoo.service.server.SLEEP_INTERVAL = 10
odoo.addons.base.ir.ir_cron._intervalTypes['minutes'] = lambda interval: relativedelta(seconds=interval * 10)

_logger = logging.getLogger(__name__)


# Ugly monkey patch to avoid incrementation of the cron nextcall
@classmethod
def _process_job(cls, job_cr, job, cron_cr):
    """ Run a given job taking care of the repetition.

    :param job_cr: cursor to use to execute the job, safe to commit/rollback
    :param job: job to be run (as a dictionary).
    :param cron_cr: cursor holding lock on the cron job row, to use to update the next exec date,
        must not be committed/rolled back!
    """
    try:
        with odoo.api.Environment.manage():
            cron = odoo.api.Environment(job_cr, job['user_id'], {})[cls._name]
            # Use the user's timezone to compare and compute datetimes,
            # otherwise unexpected results may appear. For instance, adding
            # 1 month in UTC to July 1st at midnight in GMT+2 gives July 30
            # instead of August 1st!
            now = odoo.fields.Datetime.context_timestamp(cron, datetime.now())
            nextcall = odoo.fields.Datetime.context_timestamp(cron, odoo.fields.Datetime.from_string(job['nextcall']))
            numbercall = job['numbercall']

            ok = False
            while nextcall < now and numbercall:
                if numbercall > 0:
                    numbercall -= 1
                if not ok or job['doall']:
                    cron._callback(job['cron_name'], job['ir_actions_server_id'], job['id'])
                if numbercall:
                    nextcall += odoo.addons.base.ir.ir_cron._intervalTypes[job['interval_type']](job['interval_number'])
                ok = True
            addsql = ''
            if not numbercall:
                addsql = ', active=False'
            cron_cr.execute("UPDATE ir_cron SET nextcall=%s, numbercall=%s"+addsql+" WHERE id=%s",
                            (odoo.fields.Datetime.to_string(nextcall.astimezone(pytz.UTC)), numbercall, job['id']))
            cron.invalidate_cache()
    except CronHostError:
        job_cr.rollback()
        cron_cr.rollback()
    finally:
        job_cr.commit()
        cron_cr.commit()


odoo.addons.base.ir.ir_cron.ir_cron._process_job = _process_job
