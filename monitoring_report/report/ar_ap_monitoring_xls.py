# -*- coding: utf-8 -*-
##############################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2017-TODAY Cybrosys Technologies(<http://www.cybrosys.com>).
#    Author: Jesni Banu(<https://www.cybrosys.com>)
#    you can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    It is forbidden to publish, distribute, sublicense, or sell copies
#    of the Software or modified copies of the Software.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    GENERAL PUBLIC LICENSE (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
from datetime import date, datetime, timedelta
from openerp.addons.report_xlsx.report.report_xlsx import ReportXlsx


class ar_ap_monitoring_xls(ReportXlsx):

	# def get_warehouse(self, data):
	# 	if data.get('form', False) and data['form'].get('warehouse_id', False):
	# 		l1 = []
	# 		l2 = []
	# 		obj = self.env['stock.warehouse'].search([('id', '=', data['form']['warehouse_id'])])
	# 		for j in obj:
	# 			l1.append(j.name)
	# 			l2.append(j.id)
 #        return l1, l2

	
	def get_report_type(self,data):
		if data.get('form', False) and data['form'].get('report_type', False):
			report_type = []
			cut_off_date = []
			filter_report = []
			report_type_val = data['form']['report_type']
			cut_off_date_val = data['form']['cut_off_date']
			filter_report_val = data['form']['filter_report']

			report_type.append(report_type_val)
			cut_off_date.append(cut_off_date_val)
			filter_report.append(filter_report_val)
		return report_type,cut_off_date,filter_report



	def get_partner(self,data):
		if data.get('form', False) and data['form'].get('filter_partner', False):
			partner_id = []
			obj = self.env['res.partner'].search([('id', 'in', data['form']['filter_partner'])])
			for j in obj:
				partner_id.append(j.id)
		return partner_id


	def get_lines(self,data,partner):
		lines = []
		#partner = self.get_partner(data)
		cut_off_date_val = data['form']['cut_off_date']
		filter_report_val = data['form']['filter_report']
		total_all = 0.0


		if filter_report_val == 'overdue':
			invoice_history = self.env['account.invoice'].search([('partner_id', '=', partner),
																	('state','=','open'),
																	('date_due','<',cut_off_date_val)])
		else:
			invoice_history = self.env['account.invoice'].search([('partner_id', '=', partner),
																	('state','=','open')])

			

		for x in invoice_history:
			total_all += x.amount_total
			fmt = '%Y-%m-%d'
			cut_off_date_formatted = datetime.strptime(cut_off_date_val, fmt)
			date_due_formatted =  datetime.strptime(x.date_due,fmt)
			diff_date = int(str((cut_off_date_formatted-date_due_formatted).days))

			vals = {
				'partner_name'	: x.partner_id.name,
				'invoice_name'  : x.number,
				'invoice_date'  : x.date_invoice,
				'due_date'		: x.date_due,
				'aging_day'		: diff_date,
				'currency'		: x.currency_id.name,
				'amount'		: x.amount_total,
				'amount_total'  : total_all,
			}
			lines.append(vals)
		return lines





	def generate_xlsx_report(self, workbook, data, lines):
		print "zzzzzzzzzzzzzzzzz", data
		get_report_type = self.get_report_type(data)
		get_partner = self.get_partner(data)

		sheet = workbook.add_worksheet('Stock Info')
		format1 = workbook.add_format({'font_size': 14, 'bottom': True, 'right': True, 'left': True, 'top': True, 'align': 'vcenter', 'bold': True})
		format11 = workbook.add_format({'font_size': 12, 'align': 'center', 'right': True, 'left': True, 'bottom': True, 'top': True, 'bold': True})
		format21 = workbook.add_format({'font_size': 10, 'align': 'center', 'right': True, 'left': True,'bottom': True, 'top': True, 'bold': True})
		format3 = workbook.add_format({'bottom': True, 'top': True, 'font_size': 12})
		format99 = workbook.add_format({'font_size': 10, 'align': 'center', 'bold': True})
		font_size_8 = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 10})
		red_mark = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 10,
		                                'bg_color': 'red'})
		justify = workbook.add_format({'bottom': True, 'top': True, 'right': True, 'left': True, 'font_size': 12})
		format3.set_align('center')
		font_size_8.set_align('center')
		justify.set_align('justify')
		format1.set_align('center')
		red_mark.set_align('center')

		

		sheet.write(1,0,'PT Social Bella Indonesia',format99)
		sheet.write(3,0,'Cut Off Date',format99)
		sheet.write(4,0,'Filter',format99)

		if get_report_type[0] == 'receivable':
			sheet.write(2,0,'AR Monitoring Report',format99)
		else:
			sheet.write(2,0,'AP Monitoring Report',format99)

		for i in get_report_type[1]:
			sheet.write(3,0,'Cut Off Date',format99)
			sheet.write(3,1,i,format99)

		for i in get_report_type[2]:
			sheet.write(4,0,'Filter',format99)
			sheet.write(4,1,i,format99)

		partner_row = 8
		partner_col = 0

		detail_row = 9
		detail_col = 0

		sheet.write(partner_row,detail_col,'Partner',font_size_8)
		sheet.write(partner_row,detail_col+1,'Invoice',font_size_8)
		sheet.write(partner_row,detail_col+2,'Invoice Date',font_size_8)
		sheet.write(partner_row,detail_col+3,'Due Date',font_size_8)
		sheet.write(partner_row,detail_col+4,'Aging(Days)',font_size_8)
		sheet.write(partner_row,detail_col+5,'Currency',font_size_8)
		sheet.write(partner_row,detail_col+6,'Amount',font_size_8)

		total_partner	= len(get_partner)
		for partner_count in range(0,total_partner):
			partner_idx 	= get_partner[partner_count]
			get_lines 		= self.get_lines(data, partner_idx)
			amount_total	= 0
			for i in get_lines:
				if i['aging_day'] < 0:
					sheet.write(detail_row,detail_col,i['partner_name'],format99)
					sheet.write(detail_row,detail_col+1,i['invoice_name'],format99)
					sheet.write(detail_row,detail_col+2,i['invoice_date'],format99)
					sheet.write(detail_row,detail_col+3,i['due_date'],format99)
					sheet.write(detail_row,detail_col+4,i['aging_day'],format99)
					sheet.write(detail_row,detail_col+5,i['currency'],format99)
					sheet.write(detail_row,detail_col+6,i['amount'],format99)
					amount_total += i['amount']
				else:
					sheet.write(detail_row,detail_col,i['partner_name'],red_mark)
					sheet.write(detail_row,detail_col+1,i['invoice_name'],red_mark)
					sheet.write(detail_row,detail_col+2,i['invoice_date'],red_mark)
					sheet.write(detail_row,detail_col+3,i['due_date'],red_mark)
					sheet.write(detail_row,detail_col+4,i['aging_day'],red_mark)
					sheet.write(detail_row,detail_col+5,i['currency'],red_mark)
					sheet.write(detail_row,detail_col+6,i['amount'],red_mark)
					amount_total += i['amount']
				detail_row += 1
			if get_lines:
				sheet.write(detail_row,detail_col,"TOTAL",format99)
				sheet.write(detail_row,detail_col+6,amount_total,format99)
				detail_row += 1
			
				




ar_ap_monitoring_xls('report.monitoring_report.monitoring_report_xls.xlsx', 'account.invoice')