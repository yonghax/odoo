# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from openerp import api, fields, models


class HrAdvanceRefuseWizard(models.TransientModel):

    _name = "hr.advance.refuse.wizard"
    _description = "Hr Advance refuse Reason wizard"

    description = fields.Char(string='Reason', required=True)

    @api.multi
    def advance_refuse_reason(self):
        self.ensure_one()

        context = dict(self._context or {})
        active_ids = context.get('active_ids', [])
        expense = self.env['hr.advance'].browse(active_ids)
        expense.refuse_advances(self.description)
        return {'type': 'ir.actions.act_window_close'}
