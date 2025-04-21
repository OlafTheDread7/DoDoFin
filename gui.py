# gui.py
# Simple Tkinter GUI for Personal Finance App
# RADICALLY SIMPLIFIED validation in save_action to bypass SyntaxError

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import db_utils
import csv_importer
import os
import sys
import datetime
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

ZERO_THRESHOLD = Decimal('0.005')

# --- Main Application Window Class ---
class FinanceAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("DoDoFin - Dashboard")
        self.root.geometry("500x450") # Adjusted height

        self.db_conn = None
        self.spending_var = tk.StringVar(value="$...")
        self.budget_var = tk.StringVar(value="$...")
        self.surplus_var = tk.StringVar(value="$...")
        self.debt_var = tk.StringVar(value="$...")
        self.points_var = tk.StringVar(value="...")
        self.cat_window = None
        self.current_categorization_tx = None
        self.skipped_tx_ids_session = set()
        self.cat_date_label = None; self.cat_desc_label = None; self.cat_amount_label = None; self.cat_listbox = None
        self.budget_sort_col = None; self.budget_sort_reverse = False
        self.style = ttk.Style()

        self._setup_styles()
        self._create_main_widgets()
        self._connect_db_and_load_main()

    def _setup_styles(self):
        available_themes = self.style.theme_names();
        if "vista" in available_themes: self.style.theme_use("vista")
        elif "clam" in available_themes: self.style.theme_use("clam")
        elif "aqua" in available_themes: self.style.theme_use("aqua")
        else: self.style.theme_use(available_themes[0])

    def _create_main_widgets(self):
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.dashboard_frame = ttk.LabelFrame(self.main_frame, text="Monthly Dashboard", padding="10")
        self.dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5,10))
        self.dashboard_frame.columnconfigure(1, weight=1)
        ttk.Label(self.dashboard_frame, text="Month Income:", font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky=tk.W, padx=5, pady=3); ttk.Label(self.dashboard_frame, textvariable=self.income_var, font=('Arial', 10)).grid(row=0, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Month Spending:", font=('Arial', 10, 'bold')).grid(row=1, column=0, sticky=tk.W, padx=5, pady=3); ttk.Label(self.dashboard_frame, textvariable=self.spending_var, font=('Arial', 10)).grid(row=1, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Cash Flow (Inc - Exp):", font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky=tk.W, padx=5, pady=3); self.cash_flow_label = ttk.Label(self.dashboard_frame, textvariable=self.cash_flow_var, font=('Arial', 10)); self.cash_flow_label.grid(row=2, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Month Budget Total:", font=('Arial', 10, 'bold')).grid(row=3, column=0, sticky=tk.W, padx=5, pady=3); ttk.Label(self.dashboard_frame, textvariable=self.budget_var, font=('Arial', 10)).grid(row=3, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Budget Surplus/Deficit:", font=('Arial', 10, 'bold')).grid(row=4, column=0, sticky=tk.W, padx=5, pady=3); self.budget_surplus_label = ttk.Label(self.dashboard_frame, textvariable=self.budget_surplus_var, font=('Arial', 10)); self.budget_surplus_label.grid(row=4, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Total Debt Balance:", font=('Arial', 10, 'bold')).grid(row=5, column=0, sticky=tk.W, padx=5, pady=3); ttk.Label(self.dashboard_frame, textvariable=self.debt_var, font=('Arial', 10)).grid(row=5, column=1, sticky=tk.E, padx=5, pady=3)
        ttk.Label(self.dashboard_frame, text="Gamification Points:", font=('Arial', 10, 'bold')).grid(row=6, column=0, sticky=tk.W, padx=5, pady=3); ttk.Label(self.dashboard_frame, textvariable=self.points_var, font=('Arial', 10)).grid(row=6, column=1, sticky=tk.E, padx=5, pady=3)
        self.action_frame = ttk.LabelFrame(self.main_frame, text="Actions", padding="10"); self.action_frame.pack(fill=tk.X, pady=5, side=tk.BOTTOM); self.action_frame.columnconfigure((0, 1, 2), weight=1)
        self.import_button = ttk.Button(self.action_frame, text="Import CSV", command=self.import_csv_action); self.import_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.categorize_button = ttk.Button(self.action_frame, text="Categorize", command=self.open_categorize_window); self.categorize_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.set_income_button = ttk.Button(self.action_frame, text="Set Income Est.", command=self.open_set_income_dialog); self.set_income_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.budget_button = ttk.Button(self.action_frame, text="Manage Budgets", command=self.open_budget_window); self.budget_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self.debt_button = ttk.Button(self.action_frame, text="Manage Debts", command=self.open_debt_window); self.debt_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.refresh_button = ttk.Button(self.action_frame, text="Refresh Dashboard", command=self.load_dashboard_data); self.refresh_button.grid(row=1, column=2, padx=5, pady=5, sticky="ew")
        self.status_bar = ttk.Label(self.root, text=" Ready", relief=tk.SUNKEN, anchor=tk.W); self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _connect_db_and_load_main(self):
        self.db_conn = db_utils.create_connection()
        if self.db_conn: self.set_status("DB connected. Loading dashboard..."); self.load_dashboard_data(); self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        else: error_msg = "DB Connection Failed! Run setup."; messagebox.showerror("Error", error_msg); self.set_status(error_msg); buttons=['import_button','categorize_button','budget_button','debt_button','refresh_button','set_income_button']; [getattr(self,n,None).config(state=tk.DISABLED) for n in buttons if hasattr(self,n) and getattr(self,n)]

    def set_status(self, message): self.status_bar.config(text=f" {message}"); self.root.update_idletasks()

    def load_dashboard_data(self):
        if not self.db_conn: print("DB not connected."); return
        self.set_status("Loading dashboard data...")
        try:
            today=datetime.date.today(); year, month=today.year, today.month
            inc = db_utils.get_income_total_for_month(self.db_conn, year, month); sp_dict = db_utils.get_spending_for_month(self.db_conn, year, month); spend = sum(sp_dict.values()); budg = db_utils.get_total_budgeted_expenses(self.db_conn); debts = db_utils.get_debts(self.db_conn); debt_t = sum(d['current_balance'] for d in debts); pts = db_utils.get_gamification_points(self.db_conn); cf = inc - spend; bs = budg - spend
            self.income_var.set(f"${inc:.2f}"); self.spending_var.set(f"${spend:.2f}"); self.cash_flow_var.set(f"${cf:.2f}"); self.budget_var.set(f"${budg:.2f}"); self.budget_surplus_var.set(f"${bs:.2f}"); self.debt_var.set(f"${debt_t:.2f}"); self.points_var.set(str(pts))
            try: default_fg=self.style.lookup('TLabel','foreground'); self.cash_flow_label.config(foreground="red" if cf<0 else default_fg); self.budget_surplus_label.config(foreground="red" if bs<0 else default_fg)
            except tk.TclError: self.cash_flow_label.config(foreground="black" if cf>=0 else "red"); self.budget_surplus_label.config(foreground="black" if bs>=0 else "red")
            self.set_status("Dashboard loaded.")
        except Exception as e: print(f"Error dashboard: {e}"); self.set_status("Error loading dashboard."); self.income_var.set("$ Error"); self.spending_var.set("$ Error"); self.cash_flow_var.set("$ Error"); self.budget_var.set("$ Error"); self.budget_surplus_var.set("$ Error"); self.debt_var.set("$ Error"); self.points_var.set("Error")

    def load_categories(self, listbox_widget):
        if not self.db_conn or not listbox_widget: return
        listbox_widget.delete(0, tk.END)
        try: cats = db_utils.get_categories(self.db_conn); [listbox_widget.insert(tk.END, c['name']) for c in cats] if cats else listbox_widget.insert(tk.END, "(None)")
        except Exception as e: print(f"Error loading cats: {e}"); listbox_widget.insert(tk.END, "(Error)")

    def load_debts_into_treeview(self, tree):
        if not self.db_conn or not tree: return
        for i in tree.get_children(): tree.delete(i)
        try: debts = db_utils.get_debts(self.db_conn)
            if debts: [tree.insert('',tk.END,iid=d['id'],values=(d['id'],d['name'],d['lender'] or "",f"${d['current_balance']:.2f}",f"{d['interest_rate']:.2f}",f"${d['minimum_payment']:.2f}",d['last_updated'])) for d in debts]
        except Exception as e: print(f"Error loading debts: {e}")

    def import_csv_action(self):
        if not self.db_conn: messagebox.showerror("Error", "DB disconnected."); return
        self.set_status("Select CSV..."); filetypes=(('CSV','*.csv'),('All','*.*')); fp=filedialog.askopenfilename(title='Select CSV',filetypes=filetypes)
        if not fp: self.set_status("Import cancelled."); return
        self.set_status(f"Importing {os.path.basename(fp)}...")
        try: p,u,s = csv_importer.import_csv(self.db_conn, fp); msg=f"Import done.\nProcessed: {p}\nSkipped: {s}"; messagebox.showinfo("Import", msg)
        except Exception as e: msg=f"Import Error:\n{e}"; messagebox.showerror("Error", msg); print(msg); import traceback; traceback.print_exc()
        finally: self.set_status("Import finished. Refreshing..."); self.load_dashboard_data()

    def open_categorize_window(self):
        if not self.db_conn: messagebox.showerror("Error", "DB disconnected."); return
        self.skipped_tx_ids_session=set(); self.current_categorization_tx=db_utils.get_next_uncategorized_transaction(self.db_conn,[])
        if not self.current_categorization_tx: messagebox.showinfo("Categorize", "🎉 Nothing to categorize!"); return
        self.cat_window=tk.Toplevel(self.root); self.cat_window.title("Categorize"); self.cat_window.geometry("500x550"); self.cat_window.transient(self.root); self.cat_window.grab_set(); self.cat_window.protocol("WM_DELETE_WINDOW", lambda: self._on_cat_window_close(self.cat_window))
        det_fr=ttk.LabelFrame(self.cat_window,t="Details",p="10"); det_fr.pack(p=10,f=tk.X); det_fr.columnconfigure(1,w=1)
        ttk.Label(det_fr,t="Date:",fo=('Arial',10,'bold')).grid(r=0,c=0,s=tk.W,p=5,py=2); self.cat_date_label=ttk.Label(det_fr,t=""); self.cat_date_label.grid(r=0,c=1,s=tk.W,p=5,py=2)
        ttk.Label(det_fr,t="Desc:",fo=('Arial',10,'bold')).grid(r=1,c=0,s=tk.W,p=5,py=2); self.cat_desc_label=ttk.Label(det_fr,t="",w=350); self.cat_desc_label.grid(r=1,c=1,s=tk.W,p=5,py=2)
        ttk.Label(det_fr,t="Amount:",fo=('Arial',10,'bold')).grid(r=2,c=0,s=tk.W,p=5,py=2); self.cat_amount_label=ttk.Label(det_fr,t=""); self.cat_amount_label.grid(r=2,c=1,s=tk.W,p=5,py=2)
        sel_fr=ttk.LabelFrame(self.cat_window,t="Assign Category",p="10"); sel_fr.pack(p=10,f=tk.BOTH,ex=True)
        self.cat_listbox=tk.Listbox(sel_fr,h=10,ex=False); sb=ttk.Scrollbar(sel_fr,o=tk.VERTICAL,c=self.cat_listbox.yview); self.cat_listbox.config(y=sb.set); self.cat_listbox.pack(s=tk.LEFT,f=tk.BOTH,ex=True); sb.pack(s=tk.RIGHT,f=tk.Y)
        act_fr=ttk.Frame(self.cat_window,p="10"); act_fr.pack(f=tk.X,s=tk.BOTTOM,p=5); act_fr.columnconfigure((0,1,2,3),w=1)
        ttk.Button(act_fr,t="Assign",c=self._cat_assign_action).grid(r=0,c=0,p=5,py=5,s="ew"); ttk.Button(act_fr,t="Add New",c=self._cat_add_new_action).grid(r=0,c=1,p=5,py=5,s="ew"); ttk.Button(act_fr,t="Skip",c=self._cat_skip_action).grid(r=0,c=2,p=5,py=5,s="ew"); ttk.Button(act_fr,t="Quit",c=lambda:self._on_cat_window_close(self.cat_window)).grid(r=0,c=3,p=5,py=5,s="ew")
        if not self._cat_load_next_tx(): return
        self.cat_window.lift(); self.cat_window.focus_force()

    def _cat_load_next_tx(self):
        if not self.cat_window or not self.cat_window.winfo_exists(): return False
        self.current_categorization_tx = db_utils.get_next_uncategorized_transaction(self.db_conn, list(self.skipped_tx_ids_session))
        if self.current_categorization_tx:
            self.cat_date_label.config(text=self.current_categorization_tx['transaction_date']); self.cat_desc_label.config(text=self.current_categorization_tx['description'])
            try: amt=Decimal(str(self.current_categorization_tx['amount'])).q(D('0.01')); typ="(Inc)" if self.current_categorization_tx['is_income'] else "(Exp)"; self.cat_amount_label.config(text=f"${amt:.2f} {typ}")
            except: self.cat_amount_label.config(text="Invalid Amt")
            self.load_categories(listbox_widget=self.cat_listbox); self.cat_window.update_idletasks(); return True
        else: messagebox.showinfo("Done","All categorized!",parent=self.cat_window); self._on_cat_window_close(self.cat_window); return False

    def _cat_assign_action(self):
        if not self.cat_window or not self.cat_window.winfo_exists(): return
        sel=self.cat_listbox.curselection()
        if not sel: messagebox.showwarning("Select","Please select category.",parent=self.cat_window); return
        name=self.cat_listbox.get(sel[0]); cat_id=db_utils.find_category_id_by_name(self.db_conn,name)
        if cat_id and self.current_categorization_tx:
            tx_id=self.current_categorization_tx['id'];
            if db_utils.update_transaction_category(self.db_conn,tx_id,cat_id): db_utils.add_gamification_points(self.db_conn,1); self._cat_load_next_tx()
            else: messagebox.showerror("Error","Failed update.",parent=self.cat_window)
        elif not cat_id: messagebox.showerror("Error",f"ID not found for '{name}'.",parent=self.cat_window)

    def _cat_add_new_action(self):
         if not self.cat_window or not self.cat_window.winfo_exists(): return
         name=simpledialog.askstring("Add Cat","Name:",parent=self.cat_window)
         if name and name.strip():
             new_id=db_utils.add_category(self.db_conn,name.strip())
             if new_id and self.current_categorization_tx:
                  tx_id=self.current_categorization_tx['id'];
                  if db_utils.update_transaction_category(self.db_conn,tx_id,new_id): db_utils.add_gamification_points(self.db_conn,1); self._cat_load_next_tx()
                  else: messagebox.showerror("Error","Failed assign new cat.",parent=self.cat_window)
             elif not new_id: messagebox.showerror("Error","Failed add category.",parent=self.cat_window)

    def _cat_skip_action(self):
        if not self.cat_window or not self.cat_window.winfo_exists(): return
        if self.current_categorization_tx: self.skipped_tx_ids_session.add(self.current_categorization_tx['id'])
        self._cat_load_next_tx()

    def _on_cat_window_close(self, win):
        print("Closing categorization window."); self.current_categorization_tx=None; self.skipped_tx_ids_session.clear(); self.cat_window=None; self.cat_date_label=None; self.cat_desc_label=None; self.cat_amount_label=None; self.cat_listbox=None
        if win and win.winfo_exists(): win.destroy()

    def open_debt_window(self):
        if not self.db_conn: messagebox.showerror("Error", "DB disconnected."); return
        win = tk.Toplevel(self.root); win.title("Manage Debts"); win.geometry("800x450"); win.transient(self.root); win.grab_set()
        fr = ttk.Frame(win, p="5"); fr.pack(f=tk.BOTH, ex=True, px=5, py=5)
        cols = ('id','name','lender','balance','rate','min_payment','last_updated'); tree = ttk.Treeview(fr, c=cols, show='h', h=10)
        tree.heading('id',t='ID'); tree.column('id',w=30,st=tk.NO,a=tk.CENTER); tree.heading('name',t='Name'); tree.column('name',w=170); tree.heading('lender',t='Lender'); tree.column('lender',w=120); tree.heading('balance',t='Balance'); tree.column('balance',w=100,a=tk.E); tree.heading('rate',t='Rate %'); tree.column('rate',w=60,a=tk.E); tree.heading('min_payment',t='Min Pmt'); tree.column('min_payment',w=100,a=tk.E); tree.heading('last_updated',t='Updated'); tree.column('last_updated',w=90,a=tk.CENTER)
        tree.grid(r=0,c=0,s='nsew'); sb = ttk.Scrollbar(fr,o=tk.VERTICAL,c=tree.yview); sb.grid(r=0,c=1,s='ns'); tree.configure(y=sb.set)
        fr.grid_rowconfigure(0,w=1); fr.grid_columnconfigure(0,w=1)
        def refresh(): self.load_debts_into_treeview(tree)
        bfr = ttk.Frame(win,p="5"); bfr.pack(f=tk.X,p=5); bfr.columnconfigure((0,1,2,3,4,5),w=1)
        ttk.Button(bfr, t="Add", c=lambda: self.open_add_debt_dialog(win, refresh)).grid(r=0,c=0,p=2,py=2,s="ew"); ttk.Button(bfr,t="Update",c=lambda: messagebox.showinfo("TODO","Not implemented")).grid(r=0,c=1,p=2,py=2,s="ew"); ttk.Button(bfr,t="Remove",c=lambda: messagebox.showinfo("TODO","Not implemented")).grid(r=0,c=2,p=2,py=2,s="ew"); ttk.Button(bfr,t="Strategy",c=lambda: messagebox.showinfo("TODO","Not implemented")).grid(r=1,c=0,p=2,py=2,s="ew"); ttk.Button(bfr,t="Afford Check",c=lambda: messagebox.showinfo("TODO","Not implemented")).grid(r=1,c=1,p=2,py=2,s="ew"); ttk.Button(bfr,t="Refresh",c=refresh).grid(r=1,c=2,p=2,py=2,s="ew"); ttk.Button(bfr,t="Close",c=win.destroy).grid(r=1,c=5,p=2,py=2,s="ew")
        refresh(); win.lift(); win.focus_force()

    def open_add_debt_dialog(self, parent_window, refresh_callback):
        """ Opens modal dialog to add new debt. Uses standard blocks. """
        add_dialog = tk.Toplevel(parent_window); add_dialog.title("Add New Debt"); add_dialog.geometry("350x250"); add_dialog.transient(parent_window); add_dialog.grab_set()
        form_frame = ttk.Frame(add_dialog, padding="15"); form_frame.pack(fill=tk.BOTH, expand=True)
        # Labels and Entries (Simplified creation)
        labels = ["Name:", "Lender (Optional):", "Current Balance $:", "Interest Rate %:", "Minimum Payment $:"]
        entries = {}
        for i, text in enumerate(labels):
             ttk.Label(form_frame, text=text).grid(row=i, column=0, sticky=tk.W, pady=2)
             entry = ttk.Entry(form_frame, width=30)
             entry.grid(row=i, column=1, sticky=tk.EW, pady=2)
             entries[text.split(':')[0].lower().replace(' ','_').replace('(optional)','').replace('$','').replace('%','')] = entry # Store entries by key

        # --- Save Action ---
        def save_action():
            name = entries['name'].get().strip()
            lender = entries['lender'].get().strip()
            balance_str = entries['current_balance'].get()
            rate_str = entries['interest_rate'].get()
            min_payment_str = entries['minimum_payment'].get()

            if not name:
                messagebox.showerror("Input Error", "Debt Name cannot be empty.", parent=add_dialog)
                return

            # --- DEFINITIVELY CORRECTED VALIDATION BLOCK ---
            try:
                # Convert first
                balance = Decimal(balance_str.replace('$', '').replace(',', ''))
                rate = Decimal(rate_str.replace('%', ''))
                min_payment = Decimal(min_payment_str.replace('$', '').replace(',', ''))

                # THEN check negativity on separate lines
                if balance < 0:
                    messagebox.showerror("Input Error", "Balance cannot be negative.", parent=add_dialog)
                    return
                if rate < 0:
                    messagebox.showerror("Input Error", "Interest Rate cannot be negative.", parent=add_dialog)
                    return
                if min_payment < 0:
                    messagebox.showerror("Input Error", "Minimum Payment cannot be negative.", parent=add_dialog)
                    return

            except InvalidOperation:
                # Error message on separate line
                messagebox.showerror("Input Error", "Invalid number format for Balance, Rate, or Min Payment.", parent=add_dialog)
                # Return on separate line
                return
            except Exception as e:
                # Error message on separate line
                messagebox.showerror("Input Error", f"Error processing numeric input:\n{e}", parent=add_dialog)
                # Return on separate line
                return
            # --- END DEFINITIVELY CORRECTED VALIDATION BLOCK ---

            # Proceed if validation passed
            try:
                if db_utils.add_debt(self.db_conn, name, lender or None, balance, rate, min_payment):
                    messagebox.showinfo("Success", f"Debt '{name}' added!", parent=add_dialog)
                    add_dialog.destroy()
                    refresh_callback()
                else: messagebox.showerror("Database Error", f"Failed to add debt '{name}'.\nCheck console (duplicate name?).", parent=add_dialog)
            except Exception as db_e: messagebox.showerror("Database Error", f"Error saving debt:\n{db_e}", parent=add_dialog)

        # --- Buttons ---
        button_frame_dialog = ttk.Frame(form_frame); button_frame_dialog.grid(row=len(labels), column=0, columnspan=2, pady=15)
        save_button = ttk.Button(button_frame_dialog, text="Save Debt", command=save_action); save_button.pack(side=tk.LEFT, padx=10)
        cancel_button = ttk.Button(button_frame_dialog, text="Cancel", command=add_dialog.destroy); cancel_button.pack(side=tk.LEFT, padx=10)
        form_frame.columnconfigure(1, weight=1); entries['name'].focus_set() # Focus first field

    def open_budget_window(self):
        if not self.db_conn: messagebox.showerror("Error", "DB disconnected."); return
        win=tk.Toplevel(self.root); win.title("Budgets"); win.geometry("600x450"); win.transient(self.root); win.grab_set()
        fr=ttk.Frame(win,p="5"); fr.pack(f=tk.BOTH,ex=True,px=5,py=5)
        cols=('id','name','limit'); tree=ttk.Treeview(fr,c=cols,show='h',h=10)
        tree.heading('id',t='ID',c=lambda c='id': self._on_budget_header_click(tree,c)); tree.column('id',w=60,st=tk.NO,a=tk.CENTER); tree.heading('name',t='Category',c=lambda c='name': self._on_budget_header_click(tree,c)); tree.column('name',w=250); tree.heading('limit',t='Limit',c=lambda c='limit': self._on_budget_header_click(tree,c)); tree.column('limit',w=120,a=tk.E)
        tree.grid(r=0,c=0,s='nsew'); sb=ttk.Scrollbar(fr,o=tk.VERTICAL,c=tree.yview); sb.grid(r=0,c=1,s='ns'); tree.configure(y=sb.set)
        fr.grid_rowconfigure(0,w=1); fr.grid_columnconfigure(0,w=1)
        def refresh(): self._load_budgets_and_sort(tree)
        bfr=ttk.Frame(win,p="5"); bfr.pack(f=tk.X,p=5); bfr.columnconfigure((0,1,2),w=1)
        ttk.Button(bfr,t="Set/Update",c=lambda: self._budget_open_set_dialog(tree, refresh)).grid(r=0,c=0,p=5,py=2,s="ew"); ttk.Button(bfr,t="Remove",c=lambda: messagebox.showinfo("TODO","Not implemented")).grid(r=0,c=1,p=5,py=2,s="ew"); ttk.Button(bfr,t="Refresh",c=refresh).grid(r=0,c=2,p=5,py=2,s="ew"); ttk.Button(bfr,t="Close",c=win.destroy).grid(r=1,c=2,p=5,py=2,s="ew")
        refresh(); win.lift(); win.focus_force()

    def _load_budgets_into_treeview(self, tree):
        for i in tree.get_children(): tree.delete(i)
        try: budgets=db_utils.get_budgets(self.db_conn); [tree.insert('',tk.END,iid=b['id'],values=(b['id'],b['name'],f"${b['monthly_limit']:.2f}")) for b in budgets] if budgets else None
        except Exception as e: print(f"Error loading budgets: {e}")

    def _on_budget_header_click(self, tree, col):
        rev=False
        if col==self.budget_sort_col: self.budget_sort_reverse=not self.budget_sort_reverse; rev=self.budget_sort_reverse
        else: self.budget_sort_col=col; self.budget_sort_reverse=False; rev=False
        data = []
        for iid in tree.get_children(''): v=tree.item(iid,'values');
            try: key=int(v[0]) if col=='id' else (str(v[1]).lower() if col=='name' else (Decimal(v[2][1:].replace(',','')) if col=='limit' else v[0])); data.append((key, iid))
            except: data.append((0,iid)) # Fallback
        data.sort(key=lambda x:x[0], reverse=rev); [tree.move(iid,'',idx) for idx,(key,iid) in enumerate(data)]

    def _load_budgets_and_sort(self, tree):
         col=self.budget_sort_col; rev=self.budget_sort_reverse; self._load_budgets_into_treeview(tree)
         if col: self.budget_sort_col=col; self.budget_sort_reverse=not rev; self._on_budget_header_click(tree, col)

    def _budget_open_set_dialog(self, tree, refresh_cb):
        sel = tree.selection();
        if not sel or len(sel)>1: messagebox.showwarning("Select","Select exactly one category."); return
        v=tree.item(sel[0],'values'); cat_id=int(v[0]); name=v[1]; limit_s=v[2][1:].replace(',','')
        dlg=tk.Toplevel(tree.winfo_toplevel()); dlg.title(f"Set Budget: {name}"); dlg.geometry("300x150"); dlg.transient(tree.winfo_toplevel()); dlg.grab_set()
        fr=ttk.Frame(dlg,p="15"); fr.pack(f=tk.BOTH,ex=True); ttk.Label(fr,t=f"Category: {name}").grid(r=0,c=0,cs=2,s=tk.W,p=5); ttk.Label(fr,t="New Limit $:").grid(r=1,c=0,s=tk.W,p=5); entry=ttk.Entry(fr,w=20); entry.grid(r=1,c=1,s=tk.EW,p=5); entry.insert(0,limit_s); entry.focus_set()
        def save():
            try: limit_d=Decimal(entry.get().replace('$','').replace(',',''));
                if limit_d<0: messagebox.showerror("Error","Limit must be non-negative.",parent=dlg); return
            except: messagebox.showerror("Error","Invalid number.",parent=dlg); return
            if db_utils.set_budget(self.db_conn,cat_id,limit_d): messagebox.showinfo("Success",f"Budget set to ${limit_d:.2f}",parent=dlg); dlg.destroy(); refresh_cb()
            else: messagebox.showerror("Error","Failed to set budget.",parent=dlg)
        bfr=ttk.Frame(fr); bfr.grid(r=2,c=0,cs=2,p=15); ttk.Button(bfr,t="Save",c=save).pack(s=tk.LEFT,p=10); ttk.Button(bfr,t="Cancel",c=dlg.destroy).pack(s=tk.LEFT,p=10); fr.columnconfigure(1,w=1)

    # --- Placeholder method ---
    def budget_action_placeholder(self): self.open_budget_window()

    def on_closing(self):
        print("Closing...");
        if self.db_conn:
            try: self.db_conn.close(); print("DB closed.")
            except Exception as e: print(f"Error closing DB: {e}")
        self.root.destroy()

# --- Run ---
if __name__ == "__main__":
    db_p = db_utils.DB_FILE
    if not os.path.exists(db_p): print(f"DB '{db_p}' not found. Run setup."); sys.exit(1)
    root = tk.Tk()
    app = FinanceAppGUI(root)
    root.mainloop()