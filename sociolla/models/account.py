from openerp import api, fields, models, _

class MailTemplate(models.Model):
    _inherit = ['account.config.settings']
    
    default_expense_account = fields.Many2one(
        string='Default Expense Account',
        comodel_name='account.account',
        domain=[('user_type_id','=',15)]
    )

    default_income_account = fields.Many2one(
        string='Default Income Account',
        comodel_name='account.account',
        domain=[('user_type_id','=',12)]
    )

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def update_invoice_paid(self, cr, uid, domain=None, context=None):
        move_line_obj = self.pool.get('account.move.line')

        lines = move_line_obj.browse(
            cr, 
            uid,
            move_line_obj.search(
                cr, 
                uid,
                [('full_reconcile_id', '!=', False), ('invoice_id', '!=', False)],
                context=context,
                limit=10
            ),
            context=context
        )

        for line in lines:
            line.invoice_id.confirm_paid()