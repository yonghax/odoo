from openerp import models, fields, api
from openerp.tools.translate import _
from logging import getLogger

_logger = getLogger(__name__)

class AccountDynamicFinancialReport(models.Model):
    
    _name = 'account.dynamic.financial.report'
    _description = u'Configuration Dynamic Financial Report'

    _rec_name = 'name'
    _order = 'name ASC'

    name = fields.Char(string='Name', required=True)
    
    display_name = fields.Char(
        string='Title',
        required=False,
        readonly=False,
        index=False,
        default=None,
        help=False,
        size=50,
        translate=True
    )
    
    report_type = fields.Selection(
        string='Analysis Period',
        required=True,
        default='date_range',
        help="For report like the balance sheet that do not work with date ranges",
        selection=[('date_range', 'Base on date ranges'), ('no_date_range', 'Base on single date')]
    )
    company_id = fields.Many2one('res.company', string='Company', required=True,default=lambda self: self.env['res.company']._company_default_get('account.account'))
    debit_credit = fields.Boolean(string='Show Debit and Credit',)
    
    line_ids = fields.One2many('account.dynamic.financial.report.line', 'header_id','Dynamic Financial Report Lines',)

class AccountDynamicFinancialReportLine(models.Model):

    _name = 'account.dynamic.financial.report.line' 
    _description = 'Dynamic Financial Report Details'
    _order = 'sequence ASC'

    header_id = fields.Many2one(string='Dynamic Financial Report Header',comodel_name='account.dynamic.financial.report', ondelete='cascade')
    parent_id = fields.Many2one(string='Parent',comodel_name='account.dynamic.financial.report.line', ondelete='cascade')
    children_ids = fields.One2many('account.dynamic.financial.report.line', 'parent_id', 'Children Lines')
    sequence = fields.Integer(string='Sequence',default=0,)
    level = fields.Integer(string='level',)
    name = fields.Char(string='Section Name',required=True,)    
    code = fields.Char(string='Code',required=True,)
    formulas = fields.Char(string='Formulas',default='balance = sum.balance')
    domain = fields.Char(string='Domain',)
    special_date_changer = fields.Selection(
        string='Special Date Changer',
        required=True,
        default='normal',
        selection=[('from_beginning', 'From the beginning'), ('period_start', 'At the beginning of ther period'), ('normal', 'Use given dates')]
    )

    _sql_constraints = [
        ('code_uniq', 'unique(code)', _("A code can only be used on template report !")),
    ]

