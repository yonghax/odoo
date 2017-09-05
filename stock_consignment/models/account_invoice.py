from datetime import datetime, timedelta
from openerp import api, fields, models, _
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from openerp.exceptions import UserError

class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"

    def _get_anglo_saxon_price_unit(self):
        price_unit = super(AccountInvoiceLine,self)._get_anglo_saxon_price_unit()
        product_tmpl = self.product_id.product_tmpl_id

        if price_unit > 0 and product_tmpl._get_purchase_type() == 'cons' and \
            product_tmpl.product_brand_id and product_tmpl.product_brand_id.partner_id and \
            product_tmpl.product_brand_id.partner_id.is_tax_payable and product_tmpl.product_brand_id.partner_id.default_purchase_tax:
            tax = product_tmpl.product_brand_id.partner_id.default_purchase_tax
            res_taxes = tax.compute_all(price_unit, self.company_id.currency_id, 1, product=self.product_id, partner=product_tmpl.product_brand_id.partner_id)
            price_unit = res_taxes['total_excluded']

        return price_unit