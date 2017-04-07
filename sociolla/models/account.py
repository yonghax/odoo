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