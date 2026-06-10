import { statusLabels } from './constants.jsx';

export function StatusChip({ status }) {
  const tone = ['failed', 'rejected'].includes(status)
    ? 'danger'
    : ['queued', 'running'].includes(status)
      ? 'warning'
      : ['final', 'passed', 'validated'].includes(status)
        ? 'success'
        : 'neutral';
  return <span className={`status status-${tone}`}>{statusLabels[status] || status}</span>;
}

export function DataTable({ columns, rows, empty }) {
  return (
    <div className="table-wrap" tabIndex="0" aria-label="可横向滚动的数据表">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key}>{column.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="empty-cell">
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.id}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
