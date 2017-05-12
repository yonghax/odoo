# -*- coding: utf-8 -*-

from openerp import api, fields, models


class HrAdvancePostWizard(models.TransientModel):

    _name = "hr.advance.post.wizard"
    _description = "Hr Advance generate Entries wizard"

    @api.multi
    def advance_generate_entries(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        expense = self.env['hr.advance'].browse(active_ids)
        expense.action_move_create()
        return {'type': 'ir.actions.act_window_close'}
