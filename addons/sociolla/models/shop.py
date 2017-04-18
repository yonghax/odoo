from openerp import api, fields, models, _

class SaleShop(models.Model):
    _inherit = "sale.shop"

    @api.model
    def _default_warehouse_id(self):
        company = self.env.user.company_id.id
        warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', company)], limit=1)
        return warehouse_ids

    warehouse_id = fields.Many2one(
        'stock.warehouse', 
        string='Warehouse',
        required=True,
        default=_default_warehouse_id)

    
    apply_group_id = fields.Many2one(
        string='Apply group',
        comodel_name='res.groups',
        domain=['|',('name','=','B2B'),('name','=','B2C')],
    )
    