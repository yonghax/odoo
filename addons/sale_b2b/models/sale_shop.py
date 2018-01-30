from openerp import models, fields, api

class sale_shop(models.Model):
    
    _inherit = ['sale.shop']

    sales_team_id = fields.Many2one(
        comodel_name='crm.team',
        string='Sales Team'
    )
    