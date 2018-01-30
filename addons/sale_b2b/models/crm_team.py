from openerp import models, fields, api

class crm_team(models.Model):
    _inherit = 'crm.team'

    member_ids = fields.Many2many(
        'res.users',
        'crm_team_user_rel',
        'crm_id',
        'user_id',
        string='Team Members',
        domain=[('active','=',True),]
    )