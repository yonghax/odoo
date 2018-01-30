from openerp import models, fields, api

class res_users(models.Model):
    
    _inherit = ['res.users']

    sales_team_ids = fields.Many2many(
        'crm.team',
        'crm_team_user_rel',
        'user_id',
        'crm_id',
        string='Members',
        domain=[('active','=',True),]
    )
    