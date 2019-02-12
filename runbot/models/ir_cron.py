# -*- coding: utf-8 -*-
import logging
import time
import odoo

from .repo import CronHostError

_logger = logging.getLogger(__name__)


class ir_crono(odoo.models.Model):
    """ Overrides the _callback to avoid increment of next_call """

    _inherit = "ir.cron"

    @odoo.api.model
    def _callback(self, cron_name, server_action_id, job_id):
        """ Run the method associated to a given job. It takes care of logging
        and exception handling. Note that the user running the server action
        is the user calling this method. """
        try:
            if self.pool != self.pool.check_signaling():
                # the registry has changed, reload self in the new registry
                self.env.reset()
                self = self.env()[self._name]

            log_depth = (None if _logger.isEnabledFor(logging.DEBUG) else 1)
            odoo.netsvc.log(_logger, logging.DEBUG, 'cron.object.execute', (self._cr.dbname, self._uid, '*', cron_name, server_action_id), depth=log_depth)
            start_time = False
            if _logger.isEnabledFor(logging.DEBUG):
                start_time = time.time()
            self.env['ir.actions.server'].browse(server_action_id).run()
            if start_time and _logger.isEnabledFor(logging.DEBUG):
                end_time = time.time()
                _logger.debug('%.3fs (cron %s, server action %d with uid %d)', end_time - start_time, cron_name, server_action_id, self.env.uid)
            self.pool.signal_changes()
        except CronHostError:
            """ Raised when the specific cron is tries to execute on the wrong host """
            raise
        except Exception as e:
            self.pool.reset_changes()
            _logger.exception("Call from cron %s for server action #%s failed in Job #%s",
                              cron_name, server_action_id, job_id)
            self._handle_callback_exception(cron_name, server_action_id, job_id, e)
