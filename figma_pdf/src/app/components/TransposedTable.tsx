interface Column {
  header: string;
  key: string;
}

interface TransposedTableProps {
  columns: Column[];
  data: Record<string, any>[];
}

export function TransposedTable({ columns, data }: TransposedTableProps) {
  return (
    <div className="overflow-x-auto border border-[var(--medical-navy)] rounded-lg">
      <table className="w-full">
        <tbody>
          {columns.map((column, idx) => (
            <tr
              key={column.key}
              className={idx % 2 === 0 ? "bg-[var(--medical-cream)]" : "bg-white"}
            >
              <th
                className="px-4 py-2 text-left bg-[var(--medical-navy)] text-white sticky left-0"
                style={{ minWidth: '150px' }}
              >
                {column.header}
              </th>
              {data.map((row, rowIdx) => (
                <td
                  key={rowIdx}
                  className="px-4 py-2 border-l border-[var(--medical-navy)]/20"
                  style={{ minWidth: '120px' }}
                >
                  {row[column.key] || '-'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
