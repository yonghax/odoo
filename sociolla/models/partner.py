from openerp import api, fields, models, _, SUPERUSER_ID


class partner(models.Model):
    
    _inherit = ['res.partner']

    @api.model
    def _default_shop_id(self):
        return False
        user=self.env.user
        b2b = len(user.groups_id.filtered(lambda x: x.name=='B2B')) > 0
        b2c = len(user.groups_id.filtered(lambda x: x.name=='B2C')) > 0
        
        if b2c:
            return self.env['sale.shop'].search([('name', '=', 'sociolla.com')], limit=1)

        if b2b:
            return self.env['sale.shop'].search([('name', '=', 'Sociolla BO')], limit=1)

    shop_id = fields.Many2one(string='Shop',index=True,comodel_name='sale.shop')