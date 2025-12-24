import tkinter as tk
from tkinter import ttk, messagebox
import mysql.connector

# --- CONFIGURATION ---
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "=w3-y2p!Qb45+$E",
    "database": "CraftingGameDB"
}

# --- THEME: NEXUS DARK ---
THEME = {
    "bg_main":    "#121212",  # Deep Black
    "bg_panel":   "#1e1e1e",  # Dark Grey
    "bg_slot":    "#2b2b2b",  # Slot Grey
    "bg_active":  "#383838",  # Filled Slot
    "accent":     "#bb86fc",  # Purple (Recipes)
    "highlight":  "#03dac6",  # Teal (Selection)
    "warning":    "#cf6679",  # Red (Trash/Missing)
    "drag":       "#ff9800",  # Orange (Drag Mode)
    "text":       "#e0e0e0"
}

class NexusCraftingRPG:
    def __init__(self, root):
        self.root = root
        self.root.title("Inventory System (v3.0)")
        self.root.geometry("1280x800")
        self.root.configure(bg=THEME["bg_main"])
        
        self.player_id = 1
        
        # State Management
        self.drag_source = None  # Index of slot being moved
        self.selected_slot_idx = None # Index of slot being inspected
        self.current_recipe = None
        
        self.setup_layout()
        self.refresh_inventory()

    def get_conn(self):
        return mysql.connector.connect(**DB_CONFIG)

    # =========================================
    # LAYOUT SETUP
    # =========================================
    def setup_layout(self):
        # 1. Top Bar (Creative Tools)
        top_bar = tk.Frame(self.root, bg=THEME["bg_panel"], height=50)
        top_bar.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        self.setup_top_bar(top_bar)

        # 2. Main Containers
        main_frame = tk.Frame(self.root, bg=THEME["bg_main"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # LEFT: Recipe Book (25%)
        self.left_panel = tk.Frame(main_frame, bg=THEME["bg_panel"], width=300)
        self.left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0,5))
        self.left_panel.pack_propagate(False)
        self.setup_recipe_book()

        # CENTER: Inventory Grid (45%)
        self.center_panel = tk.Frame(main_frame, bg=THEME["bg_main"])
        self.center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        self.setup_inventory_grid()

        # RIGHT: Context Panel (Workbench OR Inspector) (30%)
        self.right_panel = tk.Frame(main_frame, bg=THEME["bg_panel"], width=350)
        self.right_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5,0))
        self.right_panel.pack_propagate(False)
        
        # We stack two frames in the Right Panel and show/hide them
        self.frame_inspector = tk.Frame(self.right_panel, bg=THEME["bg_panel"])
        self.frame_workbench = tk.Frame(self.right_panel, bg=THEME["bg_panel"])
        
        self.frame_inspector.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frame_workbench.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.setup_inspector_ui()
        self.setup_workbench_ui()
        
        # Default view
        self.show_inspector_panel(empty=True)

    # =========================================
    # UI COMPONENTS
    # =========================================
    def setup_top_bar(self, parent):
        tk.Label(parent, text=" NEXUS ENGINE ", bg=THEME["bg_panel"], fg=THEME["accent"], font=("Segoe UI", 12, "bold")).pack(side=tk.LEFT, padx=10)
        
        # Spawner
        self.spawn_combo = ttk.Combobox(parent, width=15)
        self.spawn_combo.pack(side=tk.LEFT, padx=5)
        self.spawn_qty = tk.Entry(parent, width=5, bg=THEME["bg_slot"], fg="white", justify="center")
        self.spawn_qty.insert(0, "10")
        self.spawn_qty.pack(side=tk.LEFT)
        tk.Button(parent, text="+ ADD", bg=THEME["highlight"], fg="black", font=("Arial", 8, "bold"), command=self.spawn_item).pack(side=tk.LEFT, padx=5)
        
        # Load Mats for Spawner
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT item_name FROM Items i JOIN Categories c ON i.category_id=c.category_id WHERE category_name='Material'")
            self.spawn_combo['values'] = [r[0] for r in cur.fetchall()]
            conn.close()
        except: pass

    def setup_recipe_book(self):
        tk.Label(self.left_panel, text="RECIPE DATABASE", bg=THEME["bg_panel"], fg="white", font=("Segoe UI", 11, "bold")).pack(pady=10)
        
        # Search
        search_frame = tk.Frame(self.left_panel, bg=THEME["bg_panel"])
        search_frame.pack(fill=tk.X, padx=10)
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self.filter_recipes)
        tk.Entry(search_frame, textvariable=self.search_var, bg=THEME["bg_slot"], fg="white").pack(fill=tk.X)

        # Tabs
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook", background=THEME["bg_panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=THEME["bg_slot"], foreground="white", padding=[5, 2])
        style.map("TNotebook.Tab", background=[("selected", THEME["accent"])])

        self.notebook = ttk.Notebook(self.left_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=10)
        
        self.recipe_lists = {}
        for cat in ["Mats", "Gear", "Food"]:
            frame = tk.Frame(self.notebook, bg=THEME["bg_panel"])
            self.notebook.add(frame, text=cat)
            lb = tk.Listbox(frame, bg=THEME["bg_main"], fg="white", font=("Segoe UI", 10), bd=0, highlightthickness=0, selectbackground=THEME["accent"])
            lb.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            lb.bind('<<ListboxSelect>>', self.on_recipe_select)
            self.recipe_lists[cat] = lb
            
        self.load_all_recipes()

    def setup_inventory_grid(self):
        header = tk.Frame(self.center_panel, bg=THEME["bg_main"])
        header.pack(fill=tk.X, pady=10)
        tk.Label(header, text="BACKPACK", bg=THEME["bg_main"], fg="white", font=("Segoe UI", 14, "bold")).pack()
        tk.Label(header, text="(Single Click: Inspect | Double Click: Move)", bg=THEME["bg_main"], fg="#888888", font=("Arial", 8)).pack()

        self.grid_frame = tk.Frame(self.center_panel, bg=THEME["bg_main"])
        self.grid_frame.pack(expand=True)

        self.slots = []
        for i in range(20):
            # We use a Label acting as a button for better control over binding
            btn = tk.Button(self.grid_frame, text="", font=("Segoe UI Emoji", 20), 
                            width=5, height=2,
                            bg=THEME["bg_slot"], fg="white", 
                            relief="flat", bd=0)
            
            # BINDING LOGIC IS HERE
            # <Button-1> = Single Click
            # <Double-Button-1> = Double Click
            btn.bind('<Button-1>', lambda e, idx=i: self.on_slot_single_click(idx))
            btn.bind('<Double-Button-1>', lambda e, idx=i: self.on_slot_double_click(idx))
            
            row = i // 4
            col = i % 4
            btn.grid(row=row, column=col, padx=8, pady=8)
            self.slots.append(btn)
            
        tk.Button(self.center_panel, text="Auto-Sort", bg=THEME["bg_panel"], fg="white", relief="flat", command=self.auto_sort).pack(pady=10)

    # --- RIGHT PANEL A: INSPECTOR (Trash Bin) ---
    def setup_inspector_ui(self):
        # Title
        tk.Label(self.frame_inspector, text="ITEM INSPECTOR", bg=THEME["bg_panel"], fg="#888888", font=("Segoe UI", 10, "bold")).pack(pady=20)
        
        self.lbl_inspect_icon = tk.Label(self.frame_inspector, text="📦", bg=THEME["bg_panel"], fg="white", font=("Segoe UI Emoji", 48))
        self.lbl_inspect_icon.pack(pady=10)
        
        self.lbl_inspect_name = tk.Label(self.frame_inspector, text="Select an Item", bg=THEME["bg_panel"], fg="white", font=("Segoe UI", 16, "bold"), wraplength=300)
        self.lbl_inspect_name.pack()
        
        self.lbl_inspect_desc = tk.Label(self.frame_inspector, text="...", bg=THEME["bg_panel"], fg="#aaaaaa", font=("Segoe UI", 10), wraplength=300, justify="center")
        self.lbl_inspect_desc.pack(pady=10, padx=20)
        
        # TRASH BIN
        self.btn_trash = tk.Button(self.frame_inspector, text="🗑 DESTROY ITEM", 
                                   bg=THEME["warning"], fg="white", font=("Segoe UI", 10, "bold"),
                                   relief="flat", height=3, cursor="hand2", state="disabled",
                                   command=self.trash_item)
        self.btn_trash.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

    # --- RIGHT PANEL B: WORKBENCH (Crafting) ---
    def setup_workbench_ui(self):
        tk.Label(self.frame_workbench, text="WORKBENCH", bg=THEME["bg_panel"], fg=THEME["accent"], font=("Segoe UI", 10, "bold")).pack(pady=20)
        
        self.lbl_recipe_name = tk.Label(self.frame_workbench, text="Recipe Name", bg=THEME["bg_panel"], fg="white", font=("Segoe UI", 16, "bold"), wraplength=300)
        self.lbl_recipe_name.pack()

        # Dynamic Ingredients Area
        self.ing_container = tk.Frame(self.frame_workbench, bg=THEME["bg_panel"])
        self.ing_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Quantity
        qty_frame = tk.Frame(self.frame_workbench, bg=THEME["bg_panel"])
        qty_frame.pack(fill=tk.X, pady=10)
        tk.Label(qty_frame, text="Amount:", bg=THEME["bg_panel"], fg="white").pack(side=tk.LEFT, padx=(20,5))
        self.spin_craft_qty = tk.Spinbox(qty_frame, from_=1, to=999, width=5, command=self.update_craft_preview)
        self.spin_craft_qty.pack(side=tk.LEFT)
        tk.Button(qty_frame, text="MAX", bg=THEME["bg_slot"], fg=THEME["accent"], font=("Arial", 8), command=self.set_max_craft).pack(side=tk.LEFT, padx=5)

        # CRAFT BUTTON
        self.btn_craft = tk.Button(self.frame_workbench, text="CRAFT", 
                                   bg=THEME["bg_slot"], fg="grey", font=("Segoe UI", 12, "bold"),
                                   relief="flat", height=3, state="disabled",
                                   command=self.execute_craft)
        self.btn_craft.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=20)

    # =========================================
    # LOGIC: INTERACTION (CLICK / DOUBLE CLICK)
    # =========================================
    def on_slot_single_click(self, idx):
        # Case 1: We are in "Drag Mode" (Source exists) -> Swap
        if self.drag_source is not None:
            self.execute_swap(self.drag_source, idx)
            self.drag_source = None
            self.refresh_inventory() # Redraw to clear orange highlight
            return

        # Case 2: Normal Click -> Inspect
        data = self.inventory_data[idx]
        if data:
            self.selected_slot_idx = idx
            self.show_inspector_panel(data)
        else:
            self.show_inspector_panel(empty=True)
            
    def on_slot_double_click(self, idx):
        data = self.inventory_data[idx]
        if data:
            # Enter Drag Mode
            self.drag_source = idx
            # Visual Feedback: Turn Orange
            self.slots[idx].config(bg=THEME["drag"])
            # Show inspector anyway
            self.show_inspector_panel(data)
            
    def show_inspector_panel(self, data=None, empty=False):
        self.frame_inspector.lift() # Bring to front
        
        if empty:
            self.lbl_inspect_icon.config(text="📦")
            self.lbl_inspect_name.config(text="Empty Slot")
            self.lbl_inspect_desc.config(text="Double-click an item to move it.")
            self.btn_trash.config(state="disabled", bg=THEME["bg_slot"])
            self.selected_slot_idx = None
        else:
            # Icon Logic
            cat = data['category_name']
            icon = "📦"
            if "Material" in cat: icon = "🪵"
            elif "Weapon" in cat: icon = "⚔️"
            elif "Food" in cat: icon = "🍞"
            
            self.lbl_inspect_icon.config(text=icon)
            self.lbl_inspect_name.config(text=data['item_name'])
            self.lbl_inspect_desc.config(text=f"Qty: {data['quantity']}\nType: {cat}\n\n{data['description']}")
            self.btn_trash.config(state="normal", bg=THEME["warning"])

    def on_recipe_select(self, event):
        widget = event.widget
        if not widget.curselection(): return
        self.current_recipe = widget.get(widget.curselection()[0])
        
        self.frame_workbench.lift() # Show Workbench
        self.lbl_recipe_name.config(text=self.current_recipe)
        
        self.spin_craft_qty.delete(0, "end")
        self.spin_craft_qty.insert(0, 1)
        self.update_craft_preview()

    # =========================================
    # LOGIC: DATABASE OPERATIONS
    # =========================================
    def refresh_inventory(self):
        # Reset visuals
        self.inventory_data = [None] * 20
        for btn in self.slots: btn.config(text="", bg=THEME["bg_slot"])

        try:
            conn = self.get_conn()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT inv.item_id, inv.quantity, inv.slot_index, i.item_name, i.description, c.category_name 
                FROM Inventory inv 
                JOIN Items i ON inv.item_id=i.item_id 
                JOIN Categories c ON i.category_id=c.category_id 
                WHERE inv.player_id=%s AND inv.quantity > 0
            """, (self.player_id,))
            
            for row in cur.fetchall():
                idx = row['slot_index']
                if 0 <= idx < 20:
                    self.inventory_data[idx] = row
                    
                    # Mini Icon for Grid
                    icon = "📦"
                    cat = row['category_name']
                    if "Material" in cat: icon = "🪵"
                    elif "Weapon" in cat: icon = "⚔️"
                    elif "Food" in cat: icon = "🍞"
                    
                    self.slots[idx].config(text=f"{icon}\n{row['quantity']}", bg=THEME["bg_active"])
            conn.close()
        except Exception as e: print(e)

    def execute_swap(self, src, tgt):
        if src == tgt: return
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            # Swap Logic
            cur.execute("UPDATE Inventory SET slot_index=-1 WHERE player_id=%s AND slot_index=%s", (self.player_id, tgt))
            cur.execute("UPDATE Inventory SET slot_index=%s WHERE player_id=%s AND slot_index=%s", (tgt, self.player_id, src))
            cur.execute("UPDATE Inventory SET slot_index=%s WHERE player_id=%s AND slot_index=-1", (src, self.player_id))
            conn.commit()
            conn.close()
        except: pass

    def trash_item(self):
        if self.selected_slot_idx is None: return
        data = self.inventory_data[self.selected_slot_idx]
        if not data: return
        
        if messagebox.askyesno("Trash Bin", f"Permanently delete {data['quantity']} x {data['item_name']}?"):
            try:
                conn = self.get_conn()
                cur = conn.cursor()
                cur.execute("DELETE FROM Inventory WHERE player_id=%s AND slot_index=%s", (self.player_id, self.selected_slot_idx))
                conn.commit()
                conn.close()
                self.selected_slot_idx = None
                self.refresh_inventory()
                self.show_inspector_panel(empty=True)
            except Exception as e: print(e)

    def update_craft_preview(self):
        if not self.current_recipe: return
        # Clean UI
        for w in self.ing_container.winfo_children(): w.destroy()
        
        try:
            qty_mul = int(self.spin_craft_qty.get())
        except: qty_mul = 1

        try:
            conn = self.get_conn()
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT i.item_name, ri.quantity_required, 
                       IFNULL((SELECT SUM(quantity) FROM Inventory inv WHERE inv.item_id=i.item_id AND inv.player_id=%s), 0) as owned
                FROM Recipe_Ingredients ri
                JOIN Recipes r ON ri.recipe_id = r.recipe_id
                JOIN Items i ON ri.ingredient_item_id = i.item_id
                WHERE r.recipe_name = %s
            """, (self.player_id, self.current_recipe))
            
            ingredients = cur.fetchall()
            conn.close()

            can_afford = True
            self.max_craftable = 999

            for ing in ingredients:
                req = ing['quantity_required'] * qty_mul
                owned = int(ing['owned'])
                
                color = THEME["highlight"] if owned >= req else THEME["warning"]
                txt = f"{'✔' if owned >= req else '✖'} {ing['item_name']}: {owned}/{req}"
                tk.Label(self.ing_container, text=txt, bg=THEME["bg_panel"], fg=color, font=("Segoe UI", 11)).pack(anchor="w")

                if owned < req: can_afford = False
                if ing['quantity_required'] > 0:
                    possible = owned // ing['quantity_required']
                    if possible < self.max_craftable: self.max_craftable = possible

            if can_afford:
                self.btn_craft.config(state="normal", bg=THEME["highlight"], fg="black", text="CRAFT NOW")
            else:
                self.btn_craft.config(state="disabled", bg=THEME["bg_slot"], fg="grey", text="MISSING ITEMS")

        except: pass

    def execute_craft(self):
        try:
            qty = int(self.spin_craft_qty.get())
            conn = self.get_conn()
            cur = conn.cursor()
            cur.callproc('CraftItem', [self.player_id, self.current_recipe, qty])
            for res in cur.stored_results():
                row = res.fetchone()
                if row[0] == "FAIL": messagebox.showerror("Error", row[1])
                else: 
                    self.refresh_inventory()
                    self.update_craft_preview()
            conn.commit()
            conn.close()
        except Exception as e: messagebox.showerror("Error", str(e))

    def set_max_craft(self):
        if self.max_craftable > 0:
            self.spin_craft_qty.delete(0, "end")
            self.spin_craft_qty.insert(0, self.max_craftable)
            self.update_craft_preview()

    def spawn_item(self):
        item = self.spawn_combo.get()
        qty = self.spawn_qty.get()
        if not item: return
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT item_id FROM Items WHERE item_name=%s", (item,))
            iid = cur.fetchone()[0]
            # Find empty slot
            used = [x['slot_index'] for x in self.inventory_data if x]
            slot = next((i for i in range(20) if i not in used), 0)
            
            # Check if exists
            cur.execute("SELECT quantity FROM Inventory WHERE player_id=%s AND item_id=%s", (self.player_id, iid))
            if cur.fetchone():
                cur.execute("UPDATE Inventory SET quantity=quantity+%s WHERE player_id=%s AND item_id=%s", (qty, self.player_id, iid))
            else:
                cur.execute("INSERT INTO Inventory (player_id, item_id, quantity, slot_index) VALUES (%s,%s,%s,%s)", (self.player_id, iid, qty, slot))
            conn.commit()
            conn.close()
            self.refresh_inventory()
            if self.current_recipe: self.update_craft_preview()
        except: pass

    def auto_sort(self):
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT item_id FROM Inventory WHERE player_id=%s AND quantity > 0 ORDER BY item_id", (self.player_id,))
            items = cur.fetchall()
            for idx, (iid,) in enumerate(items):
                if idx < 20: cur.execute("UPDATE Inventory SET slot_index=%s WHERE player_id=%s AND item_id=%s", (idx, self.player_id, iid))
            conn.commit()
            conn.close()
            self.refresh_inventory()
        except: pass

    def load_all_recipes(self):
        # ... (Same as previous, just populates lists)
        try:
            conn = self.get_conn()
            cur = conn.cursor()
            cur.execute("SELECT r.recipe_name, c.category_name FROM Recipes r JOIN Items i ON r.crafted_item_id=i.item_id JOIN Categories c ON i.category_id=c.category_id")
            for r, c in cur.fetchall():
                if "Material" in c: self.recipe_lists["Mats"].insert(tk.END, r)
                elif "Food" in c: self.recipe_lists["Food"].insert(tk.END, r)
                else: self.recipe_lists["Gear"].insert(tk.END, r)
            conn.close()
        except: pass

    def filter_recipes(self, *args):
        # Simple search filter logic
        pass # Implemented in previous step, abbreviated here for brevity

if __name__ == "__main__":
    root = tk.Tk()
    app = NexusCraftingRPG(root)
    root.mainloop()