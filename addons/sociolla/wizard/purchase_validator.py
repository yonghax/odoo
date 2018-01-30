from openerp import models, fields, api

class purchase_validator(models.TransientModel):
    _name = 'purchase.validator.approval'
    _description = 'Approval PO Validator Wizard'

    order_id = fields.Many2one('purchase.order')
    validator_lines = fields.One2many(
        string=u'Validator Lines',
        comodel_name='purchase.validator.approval.line',
        inverse_name='purchase_validator_id',
    )

    @api.model
    def default_get(self, fields):
        res = {}
        active_id = self._context.get('active_id')
        if active_id:
            res = {'order_id': active_id}
        return res

    @api.multi
    def process(self):
        self.ensure_one()
        self.order_id.do_approve_po()

class purchase_validator_line(models.TransientModel):
    _name = 'purchase.validator.approval.line'
    _description = 'Approval PO Line Validator Wizard'
    
    purchase_validator_id = fields.Many2one(string=u'Purchase Validator',comodel_name='purchase.validator.approval',)
    purchase_order_line = fields.Many2one(string=u'Purchase Order Line',comodel_name='purchase.order.line',)
    product_id = fields.Many2one(string=u'Product',comodel_name='product.product',)
    msg_validation = fields.Char(string=u'Message Validation',)