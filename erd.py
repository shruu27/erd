"""
SQL to ERD Generator
Converts DDL SQL scripts into beautiful, presentable Entity Relationship Diagrams.
Supports: CREATE TABLE with PRIMARY KEY, FOREIGN KEY, column types, and constraints.
Output: PNG/SVG/PDF via Graphviz DOT format.
"""
 
import re
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional, Tuple
from graphviz import Digraph
 
 
# ──────────────────────────────────────────────
#  Data Models
# ──────────────────────────────────────────────
 
@dataclass
class Column:
    name: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    is_unique: bool = False
    default: Optional[str] = None
 
 
@dataclass
class ForeignKey:
    from_table: str
    from_col: str
    to_table: str
    to_col: str
 
 
@dataclass
class Table:
    name: str
    columns: list[Column] = field(default_factory=list)
    primary_keys: list[str] = field(default_factory=list)
 
 
# ──────────────────────────────────────────────
#  SQL Parser
# ──────────────────────────────────────────────
 
class DDLParser:
    """Robust regex-based DDL parser for CREATE TABLE statements."""
 
    # Matches: CREATE TABLE [IF NOT EXISTS] `name` or "name" or name
    TABLE_RE = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`"\[]?(\w+)[`"\]]?',
        re.IGNORECASE,
    )
    # Column line: name  TYPE[(size)] [NOT NULL] [DEFAULT x] [UNIQUE] [PRIMARY KEY]
    COLUMN_RE = re.compile(
        r'^\s*[`"\[]?(\w+)[`"\]]?\s+'          # col name
        r'([\w]+(?:\s*\([^)]*\))?)'             # data type (with optional size)
        r'(.*?)$',                               # rest of line
        re.IGNORECASE,
    )
    PK_INLINE_RE   = re.compile(r'\bPRIMARY\s+KEY\b', re.IGNORECASE)
    FK_CONSTRAINT_RE = re.compile(
        r'FOREIGN\s+KEY\s*\([`"\[]?(\w+)[`"\]]?\)\s*'
        r'REFERENCES\s+[`"\[]?(\w+)[`"\]]?\s*\([`"\[]?(\w+)[`"\]]?\)',
        re.IGNORECASE,
    )
    PK_CONSTRAINT_RE = re.compile(
        r'PRIMARY\s+KEY\s*\(([^)]+)\)',
        re.IGNORECASE,
    )
    NOT_NULL_RE = re.compile(r'\bNOT\s+NULL\b', re.IGNORECASE)
    UNIQUE_RE   = re.compile(r'\bUNIQUE\b', re.IGNORECASE)
    DEFAULT_RE  = re.compile(r"\bDEFAULT\s+('?[^,\s)]+'?)", re.IGNORECASE)
 
    def parse(self, sql_text: str) -> tuple[dict[str, Table], list[ForeignKey]]:
        tables: dict[str, Table] = {}
        foreign_keys: list[ForeignKey] = []
 
        # Split on CREATE TABLE boundaries
        blocks = re.split(r'(?=CREATE\s+TABLE)', sql_text, flags=re.IGNORECASE)
 
        for block in blocks:
            block = block.strip()
            if not block:
                continue
 
            m = self.TABLE_RE.match(block)
            if not m:
                continue
 
            table_name = m.group(1)
            table = Table(name=table_name)
 
            # Extract content between first ( and matching )
            body = self._extract_body(block)
            if not body:
                continue
 
            # Split into individual column/constraint definitions
            lines = self._split_definitions(body)
 
            for line in lines:
                line = line.strip().rstrip(',').strip()
                if not line:
                    continue
 
                upper = line.upper().lstrip()
 
                # ── PRIMARY KEY constraint ──
                pk_m = self.PK_CONSTRAINT_RE.search(line)
                if upper.startswith('PRIMARY') and pk_m:
                    pks = [c.strip().strip('`"[]') for c in pk_m.group(1).split(',')]
                    table.primary_keys.extend(pks)
                    continue
 
                # ── FOREIGN KEY constraint ──
                fk_m = self.FK_CONSTRAINT_RE.search(line)
                if upper.startswith(('FOREIGN', 'CONSTRAINT')) and fk_m:
                    foreign_keys.append(ForeignKey(
                        from_table=table_name,
                        from_col=fk_m.group(1),
                        to_table=fk_m.group(2),
                        to_col=fk_m.group(3),
                    ))
                    continue
 
                # ── Skip other constraints / index lines ──
                if re.match(r'^(UNIQUE|INDEX|KEY|CHECK|CONSTRAINT)\b', upper):
                    continue
 
                # ── Regular column ──
                col_m = self.COLUMN_RE.match(line)
                if col_m:
                    col_name  = col_m.group(1)
                    col_type  = col_m.group(2).strip()
                    rest      = col_m.group(3)
 
                    is_pk     = bool(self.PK_INLINE_RE.search(rest))
                    is_unique = bool(self.UNIQUE_RE.search(rest))
                    nullable  = not bool(self.NOT_NULL_RE.search(rest)) and not is_pk
                    default_m = self.DEFAULT_RE.search(rest)
                    default   = default_m.group(1) if default_m else None
 
                    if is_pk:
                        table.primary_keys.append(col_name)
 
                    table.columns.append(Column(
                        name=col_name,
                        data_type=col_type.upper(),
                        is_primary_key=is_pk,
                        is_nullable=nullable,
                        is_unique=is_unique,
                        default=default,
                    ))
 
            tables[table_name] = table
 
        # Back-fill FK flags on columns
        fk_lookup: dict[tuple[str, str], ForeignKey] = {
            (fk.from_table, fk.from_col): fk for fk in foreign_keys
        }
        for table in tables.values():
            for col in table.columns:
                if (table.name, col.name) in fk_lookup:
                    col.is_foreign_key = True
            # Mark PK columns from table-level constraint
            for pk_name in table.primary_keys:
                for col in table.columns:
                    if col.name == pk_name:
                        col.is_primary_key = True
 
        return tables, foreign_keys
 
    # ── helpers ──────────────────────────────────
 
    def _extract_body(self, block: str) -> Optional[str]:
        depth = 0
        start = None
        for i, ch in enumerate(block):
            if ch == '(':
                if depth == 0:
                    start = i + 1
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and start is not None:
                    return block[start:i]
        return None
 
    def _split_definitions(self, body: str) -> list[str]:
        """Split comma-separated definitions, respecting nested parentheses."""
        parts, current, depth = [], [], 0
        for ch in body:
            if ch == '(':
                depth += 1
                current.append(ch)
            elif ch == ')':
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current))
                current = []
            else:
                current.append(ch)
        if current:
            parts.append(''.join(current))
        return parts
 
 
# ──────────────────────────────────────────────
#  ERD Renderer  (beautiful Graphviz output)
# ──────────────────────────────────────────────
 
# Palette
COLORS = {
    "bg":           "#1E1E2E",   # canvas background
    "table_header": "#313244",   # table header fill
    "table_body":   "#2A2A3D",   # column rows fill
    "border":       "#89B4FA",   # table border
    "header_font":  "#CDD6F4",   # table name text
    "pk_row":       "#45475A",   # PK row highlight
    "pk_font":      "#F9E2AF",   # PK text (golden)
    "fk_font":      "#89DCEB",   # FK text (cyan)
    "col_font":     "#BAC2DE",   # regular column text
    "type_font":    "#6C7086",   # data type text
    "edge":         "#89B4FA",   # relationship arrow
    "edge_label":   "#A6E3A1",   # edge label text (green)
}
 
# Type → short badge
TYPE_ABBREVIATIONS = {
    "CHARACTER VARYING": "VARCHAR",
    "INTEGER":           "INT",
    "BOOLEAN":           "BOOL",
    "TIMESTAMP WITHOUT TIME ZONE": "TIMESTAMP",
    "TIMESTAMP WITH TIME ZONE":    "TIMESTAMPTZ",
    "DOUBLE PRECISION":  "FLOAT8",
}
 
 
def _abbreviate_type(t: str) -> str:
    upper = t.upper()
    for long, short in TYPE_ABBREVIATIONS.items():
        upper = upper.replace(long, short)
    return upper
 
 
def _icon(col: Column) -> str:
    if col.is_primary_key:
        return "🔑 "
    if col.is_foreign_key:
        return "🔗 "
    return "   "
 
 
def _html_table_label(table: Table) -> str:
    """Build an HTML-like label for a Graphviz node."""
    rows = []
 
    # ── Header ──────────────────────────────────
    rows.append(
        f'<TR>'
        f'<TD COLSPAN="3" BGCOLOR="{COLORS["table_header"]}" '
        f'ALIGN="CENTER" CELLPADDING="8">'
        f'<FONT FACE="Helvetica Bold" POINT-SIZE="13" '
        f'COLOR="{COLORS["header_font"]}"><B>  {table.name.upper()}  </B></FONT>'
        f'</TD>'
        f'</TR>'
    )
 
    # ── Divider ──────────────────────────────────
    rows.append(
        f'<TR>'
        f'<TD COLSPAN="3" BGCOLOR="{COLORS["border"]}" HEIGHT="1" CELLPADDING="0">'
        f'</TD>'
        f'</TR>'
    )
 
    # ── Columns ──────────────────────────────────
    for col in table.columns:
        row_bg  = COLORS["pk_row"] if col.is_primary_key else COLORS["table_body"]
        icon    = _icon(col)
        col_font = COLORS["pk_font"] if col.is_primary_key else (
                   COLORS["fk_font"] if col.is_foreign_key else COLORS["col_font"])
        type_str = _abbreviate_type(col.data_type)
        null_tag = "" if col.is_nullable else " NN"
        uniq_tag = " UQ" if col.is_unique else ""
        badge    = f"{type_str}{null_tag}{uniq_tag}"
 
        rows.append(
            f'<TR>'
            # icon cell
            f'<TD BGCOLOR="{row_bg}" ALIGN="LEFT" CELLPADDING="5" CELLSPACING="0">'
            f'<FONT FACE="Courier" POINT-SIZE="10" COLOR="{col_font}">{icon}</FONT>'
            f'</TD>'
            # name cell
            f'<TD BGCOLOR="{row_bg}" ALIGN="LEFT" CELLPADDING="5" CELLSPACING="0">'
            f'<FONT FACE="Helvetica" POINT-SIZE="11" COLOR="{col_font}"><B>{col.name}</B></FONT>'
            f'</TD>'
            # type cell
            f'<TD BGCOLOR="{row_bg}" ALIGN="RIGHT" CELLPADDING="5" CELLSPACING="0">'
            f'<FONT FACE="Courier" POINT-SIZE="9" COLOR="{COLORS["type_font"]}">{badge}</FONT>'
            f'</TD>'
            f'</TR>'
        )
 
    return '<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0" CELLPADDING="0">' \
           + ''.join(rows) + '</TABLE>>'
 
 
def generate_erd(
    ddl_statements: list[str],
    output_file: str = "erd_output",
    fmt: str = "png",
    engine: str = "dot",
) -> Tuple[Digraph, str]:
    """Parse DDL statements and render a beautiful ERD."""
 
    parser = DDLParser()
    sql_text = "\n".join(ddl_statements)
    tables, foreign_keys = parser.parse(sql_text)
 
    if not tables:
        # no tables parsed; signal error to caller rather than returning bogus value
        raise ValueError("No CREATE TABLE statements found in SQL; cannot render ERD.")
 
    # ── Graphviz setup ────────────────────────────
    dot = Digraph(
        name="ERD",
        comment="Entity Relationship Diagram",
        engine=engine,
        graph_attr={
            "bgcolor":    COLORS["bg"],
            "pad":        "0.8",
            "nodesep":    "0.9",
            "ranksep":    "1.2",
            "fontname":   "Helvetica",
            "splines":    "ortho",
            "rankdir":    "LR",   # Left → Right layout
            "concentrate":"true",
        },
        node_attr={
            "shape":     "none",
            "margin":    "0",
        },
        edge_attr={
            "color":      COLORS["edge"],
            "fontcolor":  COLORS["edge_label"],
            "fontname":   "Helvetica",
            "fontsize":   "10",
            "arrowhead":  "crow",
            "arrowtail":  "tee",
            "dir":        "both",
            "penwidth":   "1.5",
        },
    )
 
    # ── Nodes ─────────────────────────────────────
    for table in tables.values():
        dot.node(
            table.name,
            label=_html_table_label(table),
            tooltip=f"Table: {table.name} | Columns: {len(table.columns)}",
        )
 
    # ── Edges ─────────────────────────────────────
    for fk in foreign_keys:
        if fk.from_table in tables and fk.to_table in tables:
            dot.edge(
                fk.to_table,     # "one" side
                fk.from_table,   # "many" side
                label=f"  {fk.from_col} → {fk.to_col}  ",
                tooltip=f"{fk.from_table}.{fk.from_col} → {fk.to_table}.{fk.to_col}",
            )
 
    return dot, dot.source
 
 
# ──────────────────────────────────────────────
#  CLI Entry Point
# ──────────────────────────────────────────────
 
def main():
    ap = argparse.ArgumentParser(
        description="Convert SQL DDL to a beautiful ERD diagram.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sql_to_erd.py schema.sql
  python sql_to_erd.py schema.sql -o my_erd -f svg
  cat schema.sql | python sql_to_erd.py --engine neato
        """,
    )
    ap.add_argument("input", nargs="?", help="Input SQL file (defaults to stdin)")
    ap.add_argument("-o", "--output", default="erd_output",
                    help="Output file base name (default: erd_output)")
    ap.add_argument("-f", "--format", default="png",
                    choices=["png", "svg", "pdf"],
                    help="Output format (default: png)")
    ap.add_argument("-e", "--engine", default="dot",
                    choices=["dot", "neato", "fdp", "circo", "twopi"],
                    help="Graphviz layout engine (default: dot)")
    ap.add_argument("--dot-only", action="store_true",
                    help="Print DOT source and exit (do not render)")
    args = ap.parse_args()
 
    # Read SQL
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            sql_text = f.read()
    else:
        print("Reading SQL from stdin… (Ctrl-D to finish)", file=sys.stderr)
        sql_text = sys.stdin.read()
 
    ddl_statements = [sql_text]  # pass as single block for best parsing
 
    dot_obj, dot_src = generate_erd(ddl_statements, args.output, args.format, args.engine)
 
    if args.dot_only:
        print(dot_src)
        return
 
    # Render
    out_path = dot_obj.render(args.output, format=args.format, cleanup=True)
    print(f"✅  ERD rendered → {out_path}")
    print(f"   Tables found : {dot_src.count('label=<')}")
    print(f"   Format       : {args.format.upper()}")
    print(f"   Engine       : {args.engine}")
 
 
if __name__ == "__main__":
    main()
 