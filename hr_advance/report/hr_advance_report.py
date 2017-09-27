# -*- coding: utf-8 -*-

import time
from openerp.osv import osv
from openerp.tools.misc import formatLang
from openerp.tools.translate import _
from openerp.report import report_sxw
from openerp.exceptions import UserError


class report_advance(report_sxw.rml_parse):

    def set_context(self, objects, data, ids, report_type=None):
        res = super(report_advance, self).set_context(objects, data, ids, report_type=report_type)
        
        hr_advance_obj = self.pool.get('hr.advance')
        
        context = {'lang': self.pool.get('res.users').browse(self.cr, self.uid, self.uid).lang}
        state_field = hr_advance_obj.fields_get(self.cr, self.uid, 'state', context=context)['state']['selection']
        state_dict = {}
        for state_tuple in state_field:
            state_dict[state_tuple[0]] = state_tuple[1]

        advances_info = {}
        advances = hr_advance_obj.search(self.cr, self.uid, [('id', 'in', ids)], order="employee_id, currency_id, state, date")
        for advance in hr_advance_obj.browse(self.cr, self.uid, advances):
            key = advance.employee_id.name + '-' + advance.currency_id.name + '-' + advance.state
            if advances_info.get(key):
                advances_info[key]['lines'] += advance
                advances_info[key]['total_amount'] += advance.amount
            else:
                advances_info[key] = {
                                        'employee_name': advance.employee_id.name, 
                                        'total_amount': advance.amount, 
                                        'lines': advance,
                                        'currency': advance.currency_id,
                                        'validator_name': advance.employee_id.parent_id.name,
                                        'notes': [],
                                        'notes_index': {},
                                        'state': state_dict[advance.state],
                                    }
            if advance.description:
                index = len(advances_info[key]['notes']) + 1
                advances_info[key]['notes'].append({'description': advance.description, 'index':index})
                advances_info[key]['notes_index'][advance.id] = index

        # Qweb for-each do not work on dict, so we send a list and we sort it by the name of the employee
        # that way if we have two sheet for the same employee they will follow in the report
        self.localcontext.update({
            'get_advances': lambda : [v for k,v in sorted(advances_info.items())],
            })
        return res


class report_hr_advance(osv.AbstractModel):
    _name = 'report.hr_advance.report_advance'
    _inherit = 'report.abstract_report'
    _template = 'hr_advance.report_advance'
    _wrapped_report_class = report_advance
