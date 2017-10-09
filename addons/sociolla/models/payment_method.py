from openerp import api, fields, models, _

class PaymentMethod(models.Model):
    _name='sociolla.payment.method'
    
    name = fields.Char(string='Name',required=True,)
    partner_id = fields.Many2one(
        string='Partner',
        required=True,
        change_default=True,
        comodel_name='res.partner',
        domain=[('customer','=',True)],
    )
    payment_term_id = fields.Many2one(
        string='Payment Term',
        required=True,
        readonly=False,
        comodel_name='account.payment.term',
    )

    @api.onchange('partner_id')
    def _setPaymentTerm(self):
        if self.partner_id:
            self.payment_term_id = self.partner_id.property_payment_term_id
    