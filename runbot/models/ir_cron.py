# -*- coding: utf-8 -*-
import logging
import time
import odoo

from .repo import CronHostError

_logger = logging.getLogger(__name__)


class ir_cron(odoo.models.Model):
    """ Overrides the _callback to avoid increment of next_call """

    _inherit = "ir.cron"

    @odoo.api.model
    def _handle_callback_exception(self, cron_name, server_action_id, job_id, job_exception):
        super()._handle_callback_exception(cron_name, server_action_id, job_id, job_exception)
        if isinstance(job_exception, CronHostError):
            raise job_exception
