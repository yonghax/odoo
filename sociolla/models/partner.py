from openerp import api, fields, models, _, SUPERUSER_ID


class partner(models.Model):
    
    _inherit = ['res.partner']
    
    default_purchase_tax = fields.Many2one(
        string='Default Purchase Tax',
        comodel_name='account.tax',
        domain=[('type_tax_use', '=', 'purchase')],
        ondelete='cascade',
        auto_join=False
    )