# -*- coding: utf-8 -*-

from openerp import api, models
from openerp.tools import float_compare

class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.multi
    def reconcile(self, writeoff_acc_id=False, writeoff_journal_id=False):
        res = super(AccountMoveLine, self).reconcile(writeoff_acc_id=writeoff_acc_id, writeoff_journal_id=writeoff_journal_id)
        account_move_ids = [l.move_id.id for l in self if float_compare(l.move_id.matched_percentage, 1, precision_digits=5) == 0]
        if account_move_ids:
            advances = self.env['hr.advance'].search([('account_move_id', 'in', account_move_ids)])
            advances.reconciled_advances()
        return res
