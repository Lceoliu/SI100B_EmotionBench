import { statusLabels } from './constants.jsx';
import { Fragment } from 'react';

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

export function DataTable({ columns, rows, empty, expandedRowId, onRowClick, renderExpanded, getRowClassName }) {
  function handleRowClick(event, row) {
    if (!onRowClick) return;
    if (event.target.closest('button, a, input, select, textarea')) return;
    onRowClick(row);
  }

  function handleRowKeyDown(event, row) {
    if (!onRowClick || !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    onRowClick(row);
  }

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
            rows.map((row) => {
              const expanded = expandedRowId === row.id;
              const customClass = getRowClassName?.(row) || '';
              const rowClass = [onRowClick ? 'clickable-row' : '', expanded ? 'expanded' : '', customClass].filter(Boolean).join(' ');
              return (
                <Fragment key={row.id}>
                  <tr
                    className={rowClass}
                    onClick={(event) => handleRowClick(event, row)}
                    onKeyDown={(event) => handleRowKeyDown(event, row)}
                    tabIndex={onRowClick ? 0 : undefined}
                    aria-expanded={onRowClick ? expanded : undefined}
                  >
                    {columns.map((column) => (
                      <td key={column.key}>{column.render ? column.render(row) : row[column.key]}</td>
                    ))}
                  </tr>
                  {renderExpanded && expanded && (
                    <tr className="expanded-row">
                      <td colSpan={columns.length}>{renderExpanded(row)}</td>
                    </tr>
                  )}
                </Fragment>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
