from datetime import date, datetime

from openerp import api, fields, models, SUPERUSER_ID, _
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.float_utils import float_compare, float_round

class stock_quant(models.Model):
    _inherit = 'stock.quant'
    _order = 'in_date'

    is_switchover_stock = fields.Boolean(string='Switchover stock')

    def _quant_create(self, cr, uid, qty, move, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False,
                      force_location_from=False, force_location_to=False, context=None):
        '''Create a quant in the destination location and create a negative quant in the source location if it's an internal location.
        '''
        if context is None:
            context = {}
        price_unit = self.pool.get('stock.move').get_price_unit(cr, uid, move, context=context)
        location = force_location_to or move.location_dest_id
        rounding = move.product_id.uom_id.rounding
        vals = {
            'product_id': move.product_id.id,
            'location_id': location.id,
            'qty': float_round(qty, precision_rounding=rounding),
            'cost': price_unit,
            'history_ids': [(4, move.id)],
            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'company_id': move.company_id.id,
            'lot_id': lot_id,
            'owner_id': owner_id,
            'package_id': dest_package_id,
            'is_switchover_stock': move.is_switchover_stock,
        }
        if move.location_id.usage == 'internal':
            #if we were trying to move something from an internal location and reach here (quant creation),
            #it means that a negative quant has to be created as well.
            negative_vals = vals.copy()
            negative_vals['location_id'] = force_location_from and force_location_from.id or move.location_id.id
            negative_vals['qty'] = float_round(-qty, precision_rounding=rounding)
            negative_vals['cost'] = price_unit
            negative_vals['negative_move_id'] = move.id
            negative_vals['package_id'] = src_package_id
            negative_quant_id = self.create(cr, SUPERUSER_ID, negative_vals, context=context)
            vals.update({'propagated_from_id': negative_quant_id})

        picking_type = move.picking_id and move.picking_id.picking_type_id or False
        if lot_id and move.product_id.tracking == 'serial' and (not picking_type or (picking_type.use_create_lots or picking_type.use_existing_lots)):
            if qty != 1.0:
                raise UserError(_('You should only receive by the piece with the same serial number'))

        #create the quant as superuser, because we want to restrict the creation of quant manually: we should always use this method to create quants
        quant_id = self.create(cr, SUPERUSER_ID, vals, context=context)
        quant = self.browse(cr, uid, quant_id, context=context)
        if move.product_id.valuation == 'real_time':
            self._account_entry_move(cr, uid, [quant], move, context)

            # If the precision required for the variable quant cost is larger than the accounting
            # precision, inconsistencies between the stock valuation and the accounting entries
            # may arise.
            # For example, a box of 13 units is bought 15.00. If the products leave the
            # stock one unit at a time, the amount related to the cost will correspond to
            # round(15/13, 2)*13 = 14.95. To avoid this case, we split the quant in 12 + 1, then
            # record the difference on the new quant.
            # We need to make sure to able to extract at least one unit of the product. There is
            # an arbitrary minimum quantity set to 2.0 from which we consider we can extract a
            # unit and adapt the cost.
            curr_rounding = move.company_id.currency_id.rounding
            cost_rounded = float_round(quant.cost, precision_rounding=curr_rounding)
            cost_correct = cost_rounded
            if float_compare(quant.product_id.uom_id.rounding, 1.0, precision_digits=1) == 0\
                    and float_compare(quant.qty * quant.cost, quant.qty * cost_rounded, precision_rounding=curr_rounding) != 0\
                    and float_compare(quant.qty, 2.0, precision_rounding=quant.product_id.uom_id.rounding) >= 0:
                qty = quant.qty
                cost = quant.cost
                quant_correct = quant_obj._quant_split(cr, uid, quant, quant.qty - 1.0, context=context)
                cost_correct += (qty * cost) - (qty * cost_rounded)
                quant_obj.write(cr, SUPERUSER_ID, [quant.id], {'cost': cost_rounded}, context=context)
                quant_obj.write(cr, SUPERUSER_ID, [quant_correct.id], {'cost': cost_correct}, context=context)
        return quant

    def _account_entry_move(self, cr, uid, quants, move, context=None):
        if move.inventory_id:
            if not move.is_switchover_stock:
                self._account_entry_move_adjustment(quants, move, context)
        else:
            super(stock_quant, self)._account_entry_move(cr, uid, quants, move, context=context)
        
        return False

    def _account_entry_move_adjustment(self, quants, move, context=None):
        if context is None:
            context = {}
        cr = move._cr
        uid = move._uid
        location_obj = self.pool.get('stock.location')
        location_from = move.location_id
        location_to = quants[0].location_id
        company_from = location_obj._location_owner(cr, uid, location_from, context=context)
        company_to = location_obj._location_owner(cr, uid, location_to, context=context)

        if move.product_id.valuation != 'real_time':
            return False
        for q in quants:
            # if q.owner_id:
            #     #if the quant isn't owned by the company, we don't make any valuation entry
            #     return False
            if q.qty <= 0:
                #we don't make any stock valuation for negative quants because the valuation is already made for the counterpart.
                #At that time the valuation will be made at the product cost price and afterward there will be new accounting entries
                #to make the adjustments when we know the real cost price.
                return False

        #in case of routes making the link between several warehouse of the same company, the transit location belongs to this company, so we don't need to create accounting entries
        # Create Journal Entry for products arriving in the company
        if company_to and (move.location_id.usage not in ('internal', 'transit') and move.location_dest_id.usage == 'internal' or company_from != company_to) and move.product_id.product_tmpl_id._get_purchase_type() != 'cons':
            ctx = context.copy()
            ctx['force_company'] = company_to.id
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)

            adj_account = move.product_id.property_account_inv_adjustment_in_id.id or move.product_id.categ_id.property_account_inv_adjustment_in_categ_id.id
            self._create_account_move_line(cr, uid, quants, move, adj_account, acc_valuation, journal_id, context=ctx)

        # Create Journal Entry for products leaving the company
        if company_from and (move.location_id.usage == 'internal' and move.location_dest_id.usage not in ('internal', 'transit') or company_from != company_to):
            ctx = context.copy()
            ctx['force_company'] = company_from.id
            journal_id, acc_src, acc_dest, acc_valuation = self._get_accounting_data_for_valuation(cr, uid, move, context=ctx)

            adj_account = move.product_id.property_account_inv_adjustment_out_id.id or move.product_id.categ_id.property_account_inv_adjustment_out_categ_id.id
            if move.product_id.product_tmpl_id._get_purchase_type() == 'cons':
                credit_account_id = move.product_id.product_brand_id.partner_id.property_account_payable_id.id
                debit_account_id = move.product_id.property_account_expense_id.id or move.product_id.categ_id.property_account_expense_categ_id.id
                self._create_account_move_line(cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=ctx)
            else:
                self._create_account_move_line(cr, uid, quants, move, acc_valuation, adj_account, journal_id, context=ctx)

    def _create_account_move_line(self, cr, uid, quants, move, credit_account_id, debit_account_id, journal_id, context=None):
        #group quants by cost
        from openerp.osv import fields, osv
        quant_cost_qty = {}
        for quant in quants:
            if quant_cost_qty.get(quant.cost):
                quant_cost_qty[quant.cost] += quant.qty
            else:
                cost = quant.cost
                if cost == 0 and move.product_id.product_tmpl_id._get_purchase_type() == 'cons':
                    cost = move.inventory_line_id.standard_price

                quant_cost_qty[cost] = quant.qty
        move_obj = self.pool.get('account.move')
        for cost, qty in quant_cost_qty.items():
            move_lines = self._prepare_account_move_line(cr, uid, move, qty, cost, credit_account_id, debit_account_id, context=context)
            if move_lines:
                date = context.get('force_period_date', fields.date.context_today(self, cr, uid, context=context))
                new_move = move_obj.create(cr, uid, {'journal_id': journal_id,
                                          'line_ids': move_lines,
                                          'date': date,
                                          'ref': move.picking_id.name}, context=context)
                move_obj.post(cr, uid, [new_move], context=context)
                if move.inventory_id:
                    move.inventory_id.write({'account_move_id': [(4, [new_move])]}) 
                