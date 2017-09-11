from openerp.osv import fields, osv
from openerp.tools import float_compare, float_round
from openerp.tools.translate import _
from openerp import SUPERUSER_ID, api, models
from openerp.exceptions import UserError
import logging

from itertools import groupby
from operator import itemgetter

_logger = logging.getLogger(__name__)

class stock_inventory_line(models.Model):
    
    _inherit = ['stock.inventory.line']

    def onchange_createline(self, cr, uid, ids, location_id=False, product_id=False, uom_id=False, package_id=False, prod_lot_id=False, partner_id=False, company_id=False, context=None):
        quant_obj = self.pool["stock.quant"]
        uom_obj = self.pool["product.uom"]
        res = {'value': {}}
        # If no UoM already put the default UoM of the product
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            uom = self.pool['product.uom'].browse(cr, uid, uom_id, context=context)
            if product.uom_id.category_id.id != uom.category_id.id:
                res['value']['product_uom_id'] = product.uom_id.id
                res['domain'] = {'product_uom_id': [('category_id','=',product.uom_id.category_id.id)]}
                uom_id = product.uom_id.id
        # Calculate theoretical quantity by searching the quants as in quants_get
        if product_id and location_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            if not company_id:
                company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
            dom = [('company_id', '=', company_id), ('location_id', '=', location_id), ('lot_id', '=', prod_lot_id),
                        ('product_id','=', product_id), ('package_id', '=', package_id)]
            quants = quant_obj.search(cr, uid, dom, context=context)
            th_qty = sum([x.qty for x in quant_obj.browse(cr, uid, quants, context=context)])
            if product_id and uom_id and product.uom_id.id != uom_id:
                th_qty = uom_obj._compute_qty(cr, uid, product.uom_id.id, th_qty, uom_id)
            res['value']['theoretical_qty'] = th_qty
            res['value']['product_qty'] = th_qty
        return res

    # def _get_theoretical_qty(self, cr, uid, ids, name, args, context=None):
    #     res = {}
    #     quant_obj = self.pool["stock.quant"]
    #     uom_obj = self.pool["product.uom"]
    #     for line in self.browse(cr, uid, ids, context=context):
    #         quant_ids = self._get_quants(cr, uid, line, context=context)
    #         quants = quant_obj.browse(cr, uid, quant_ids, context=context)
    #         tot_qty = sum([x.qty for x in quants])
    #         if line.product_uom_id and line.product_id.uom_id.id != line.product_uom_id.id:
    #             tot_qty = uom_obj._compute_qty_obj(cr, uid, line.product_id.uom_id, tot_qty, line.product_uom_id, context=context)
    #         res[line.id] = tot_qty
    #     return res
    

class stock_quant(osv.osv):
    _inherit = 'stock.quant'

    def _account_entry_move(self, cr, uid, quants, move, context=None):
        if not move.is_switchover_stock and move.product_id.valuation == 'real_time':
            super(stock_quant, self)._account_entry_move(cr, uid, quants, move, context=context)
            
            quants = filter(lambda x: x.owner_id, quants) #quants.filtered(lambda x: x.owner_id)
            if len(quants) < 1:
                return
            if context is None:
                context = {}

            location_obj = self.pool.get('stock.location')
            location_from = move.location_id
            location_to = quants[0].location_id
            company_from = location_obj._location_owner(cr, uid, location_from, context=context)
            company_to = location_obj._location_owner(cr, uid, location_to, context=context)

            if location_to and location_to.usage == 'customer' and company_from and (move.location_id.usage == 'internal' and move.location_dest_id.usage not in ('internal', 'transit') or company_from != company_to):
                ctx = context.copy()
                ctx['force_company'] = company_from.id
                journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)
                
                # Create Journal Entry for products leaving the company
                if company_from and (move.location_id.usage == 'internal' and move.location_dest_id.usage not in ('internal', 'transit') or company_from != company_to):
                    journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)
                    if location_to and location_to.usage == 'customer':
                        res_quants = dict((k, [v for v in itr]) for k, itr in groupby(sorted(quants, key=itemgetter(*['owner_id'])), itemgetter(*['owner_id'])))
                        for owner_id, quants in res_quants.items():
                            self._create_journal_consignment(cr, uid, owner_id, quants, move, acc_dest, journal_id, context=ctx)
    
    def _create_journal_consignment(self, cr, uid, owner_id, quants, move, stock_out_account, journal_id, context=None):
        #group quants by owner
        quant_cost_qty = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
            else:
                quant_cost_qty[quant.cost] = quant.qty
        move_obj = self.pool.get('account.move')
        for cost, qty in quant_cost_qty.items():
            move_lines = self._prepare_account_move_line_consignment(cr, uid, move, owner_id, qty, cost, stock_out_account, owner_id.property_account_payable_id.id, owner_id.default_purchase_tax, context=context)
            if move_lines:
                date = context.get('force_period_date', fields.date.context_today(self, cr, uid, context=context))
                new_move = move_obj.create(cr, uid, {'journal_id': journal_id,
                                            'line_ids': move_lines,
                                            'date': date,
                                            'ref': move.picking_id.name}, context=context)
                move_obj.post(cr, uid, [new_move], context=context)

    def _prepare_account_move_line_consignment(self, cr, uid, move, owner_id, qty, cost, stock_out_account, account_payable_id, default_purchase_tax, context=None):
        if context is None:
            context = {}
        currency_obj = self.pool.get('res.currency')

        if context.get('force_valuation_amount'):
            valuation_amount = context.get('force_valuation_amount')
        else:
            if move.product_id.cost_method == 'average':
                valuation_amount = cost if move.location_id.usage != 'internal' and move.location_dest_id.usage == 'internal' else move.product_id.standard_price
            else:
                valuation_amount = cost if move.product_id.cost_method == 'real' else move.product_id.standard_price

        valuation_amount = currency_obj.round(cr, uid, move.company_id.currency_id, valuation_amount * qty)
        untaxed_amount = valuation_amount
        tax_amount = 0

        if default_purchase_tax:
            taxes = default_purchase_tax.compute_all(valuation_amount / qty, move.company_id.currency_id, qty, product=move.product_id, partner=owner_id)
            
            valuation_amount = taxes['total_included']
            tax_amount = taxes['total_included'] - taxes['total_excluded']
            untaxed_amount = taxes['total_excluded']

        if move.company_id.currency_id.is_zero(valuation_amount):
            if move.product_id.cost_method == 'standard':
                raise UserError(_("The found valuation amount for product %s is zero. Which means there is probably a configuration error. Check the costing method and the standard price") % (move.product_id.name,))
            else:
                return []

        partner_id = (move.picking_id.partner_id and self.pool.get('res.partner')._find_accounting_partner(move.picking_id.partner_id).id) or False

        stock_out_vals = {
            'name': move.name,
            'product_id': move.product_id.id,
            'quantity': qty,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': move.picking_id and move.picking_id.name or False,
            'partner_id': partner_id,
            'debit': untaxed_amount > 0 and untaxed_amount or 0,
            'credit': untaxed_amount < 0 and -untaxed_amount or 0,
            'account_id': stock_out_account,
        }

        payable_line_vals = {
            'name': move.name,
            'product_id': move.product_id.id,
            'quantity': qty,
            'product_uom_id': move.product_id.uom_id.id,
            'ref': move.picking_id and move.picking_id.name or False,
            'partner_id': owner_id.id,
            'credit': valuation_amount > 0 and valuation_amount or 0,
            'debit': valuation_amount < 0 and -valuation_amount or 0,
            'account_id': account_payable_id,
        }

        if tax_amount > 0:
            tax_line_vals = {
                'name': move.name,
                'product_id': move.product_id.id,
                'quantity': qty,
                'product_uom_id': move.product_id.uom_id.id,
                'ref': move.picking_id and move.picking_id.name or False,
                'partner_id': owner_id.id,
                'debit': tax_amount > 0 and tax_amount or 0,
                'credit': tax_amount < 0 and -tax_amount or 0,
                'account_id': default_purchase_tax.account_id.id,
            }
            return [(0, 0, stock_out_vals), (0, 0, tax_line_vals), (0, 0, payable_line_vals)]

        return [(0, 0, stock_out_vals), (0, 0, payable_line_vals)]