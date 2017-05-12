# -*- coding: utf-8 -*-

from openerp import api, fields, models


class HrExpensePostWizard(models.TransientModel):

    _name = "hr.expense.post.wizard"
    _description = "Hr Expense generate Entries wizard"

    @api.multi
    def expense_generate_entries(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        expense = self.env['hr.expense'].browse(active_ids)
        expense.action_move_create()
        return {'type': 'ir.actions.act_window_close'}
