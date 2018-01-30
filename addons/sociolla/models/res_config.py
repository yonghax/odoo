from datetime import datetime

from openerp import api, fields, models, _, SUPERUSER_ID
import openerp.addons.decimal_precision as dp

class company(models.Model):
    _inherit = ['res.company']
        
    default_expense_account = fields.Many2one(
        string='Default Expense Account',
        comodel_name='account.account',
        domain=[('user_type_id','=',15)]
    )

    default_income_account = fields.Many2one(
        string='Default Expense Account',
        comodel_name='account.account',
        domain=[('user_type_id','=',12)]
    )

    default_discount_account = fields.Many2one(
        string='Default Expense Account',
        comodel_name='account.account',
        domain=[('user_type_id','=',27)]
    )
    
class AccountingSetting(models.TransientModel):
    _inherit = ['account.config.settings']
    
    default_expense_account = fields.Many2one(
        string='Default Expense Account',
        comodel_name='account.account',
        related='company_id.default_expense_account',
        inverse='_set_default_expense_account',
        domain=[('user_type_id','=',15)]
    )

    default_income_account = fields.Many2one(
        string='Default Income Account',
        comodel_name='account.account',
        related='company_id.default_income_account',
        inverse='_set_default_income_account',
        domain=[('user_type_id','=',12)]
    )

    default_discount_account = fields.Many2one(
        string='Default Income Account',
        comodel_name='account.account',
        related='company_id.default_discount_account',
        inverse='_set_default_discount_account',
        domain=[('user_type_id','=',27)]
    )

    @api.one
    def _set_default_expense_account(self):
        if self.default_expense_account != self.company_id.default_expense_account:
            self.company_id.default_expense_account = self.default_expense_account

    @api.one
    @api.depends('company_id')
    def _get_default_expense_account(self):
        self.default_expense_account = self.company_id.default_expense_account

    @api.one
    def _set_default_income_account(self):
        if self.default_income_account != self.company_id.default_income_account:
            self.company_id.default_income_account = self.default_income_account

    @api.one
    @api.depends('company_id')
    def _get_default_income_account(self):
        self.default_income_account = self.company_id.default_income_account

    @api.one
    def _set_default_discount_account(self):
        if self.default_discount_account != self.company_id.default_discount_account:
            self.company_id.default_discount_account = self.default_discount_account

    @api.one
    @api.depends('company_id')
    def _get_default_discount_account(self):
        self.default_discount_account = self.company_id.default_discount_account