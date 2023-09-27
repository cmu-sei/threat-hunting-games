import string

class Matrix:

    def __init__(self):
        self._rows = {}
        self._col_keys = set()

    def row(self, row_key):
        if row_key not in self._rows:
            row = self._rows[row_key] = {}
            for col_key in self._col_keys:
                row[col_key] = 0
        return self._rows[row_key]

    def col(self, col_key):
        if col_key not in self._col_keys:
            self._col_keys.add(col_key)
            for row in self._rows.values():
                row[col_key] = 0
        col = {}
        for row_key, val in self._rows.items():
            col[row_key] = val
        return col

    def as_matrix(self):
        rows = []
        col_keys = sorted(self._col_keys)
        col_names = ['']
        col_names.extend(self.col_name(x) for x in col_keys)
        rows.append(col_names)
        for row_key in sorted(self._rows):
            row = [self.row_name(row_key)]
            for col_key in col_keys:
                row.append(self._rows[row_key][col_key])
            rows.append(row)
        return rows

    def cols(self):
        cols = {}
        for col_key in self._col_keys:
            cols[col_key] = self.col(col_key)
        return cols

    def inc_val(self, row_key, col_key, incr):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        self._rows[row_key][col_key] += incr
        return self._rows[row_key][col_key]

    def set_val(self, row_key, col_key, val):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        self._rows[row_key][col_key] = val
        return val

    def val(self, row_key, col_key):
        # make sure row/col exist
        row = self.row(row_key)
        self.col(col_key)
        return self._rows[row_key][col_key]

    def contains_row(self, row_key):
        return row_key in self._rows

    def contains_col(self, col_key):
        return col_key in self._col_keys

    def row_name(self, row_key):
        assert row_key in self._rows, f"unknown row: {row_key}"
        name = row_key
        if not isinstance(name, str):
            name = '-'.join(x for x in name if x)
        return name

    def col_name(self, col_key):
        assert col_key in self._rows, f"unknown col: {col_key}"
        name = col_key
        if not isinstance(name, str):
            name = '-'.join(x for x in name if x)
        return name

    def __getitem__(self, row_key):
        return self._rows[row_key]


class Sheet:

    def __init__(self, key, preamble=None):
        self._key = key
        self._preamble = preamble
        self._atk_matrix = Matrix()
        self._def_matrix = Matrix()
        self._rows = {}
        self._col_keys = set()

    @property
    def preamble(self):
        return self._preamble

    @property
    def atk_matrix(self):
        return self._atk_matrix

    @property
    def def_matrix(self):
        return self._def_matrix

    @property
    def key(self):
        return self._key

    @property
    def name(self):
        name = self._key
        if not isinstance(name, str):
            name = '-'.join(name)
        return name

    def dump_csv(self, writer):
        # note: does not save the csv file
        if self._preamble:
            for row in self._preamble:
                writer.writerow(row)
            # blank row
            writer.writerow([])
        for row in self.atk_matrix.as_matrix():
            writer.writerow(row)
        # blank row
        for row in self.def_matrix.as_matrix():
            writer.writerow(row)

    def dump_xlsx(self, xls_sheet):
        # note: does not save the workbook
        xl_cols = string.ascii_uppercase
        def _col_idx(int_idx):
            quotient, remainder = divmod(int_idx, len(xl_cols))
            letter = xl_cols[remainder]
            if quotient:
                letter = letter * (quotient + 1)
            return letter
        def _cell_name(row_idx, col_idx):
            col_letter = _col_idx(col_idx)
            cell_name = f"{col_letter}{row_idx}"
            return cell_name
        row_idx = 1
        if self._preamble:
            for row in self._preamble:
                for i, val in enumerate(row):
                    cell_name = _cell_name(row_idx, i)
                    xls_sheet[cell_name] = val
                row_idx += 1
            row_idx += 1 # blank row
        xls_sheet[_cell_name(row_idx, 0)] = "Attacker Matrix"
        row_idx += 1 # blank row
        for row in self.atk_matrix.as_matrix():
            for i, val in enumerate(row):
                cell_name = _cell_name(row_idx, i)
                xls_sheet[cell_name] = val
            row_idx += 1
        row_idx += 1 # blank row
        xls_sheet[_cell_name(row_idx, 0)] = "Defender Matrix"
        row_idx += 1 # blank_row
        for row in self.def_matrix.as_matrix():
            for i, val in enumerate(row):
                cell_name = _cell_name(row_idx, i)
                xls_sheet[cell_name] = val
            row_idx += 1

    def __key__(self):
        return self._key


class Sheets:

    def __init__(self):
        self._sheets = {}

    def sheet(self, sheet_key):
        if sheet_key not in self._sheets:
            self._sheets[sheet_key] = Sheet(sheet_key)
        return self._sheets[sheet_key]

    def sheet_names(self):
        return sorted(self._sheets)

    def sheets(self):
        sheets = []
        for name in self.sheet_names():
            sheets.append(self._sheets[name])
        return sheets

    def __contains__(self, sheet_key):
        return sheet_key in self._sheets
