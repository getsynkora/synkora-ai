'use client'

import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  type ChartOptions,
} from 'chart.js'
import { Line, Bar, Pie, Doughnut, Scatter } from 'react-chartjs-2'
import type { ChartData } from '../ChartRenderer'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
)

export function ChartJSRenderer({ chart }: { chart: ChartData }) {
  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'top' },
      title: { display: false },
    },
    ...(chart.config as object),
  }
  const chartData = chart.data
  if (!chartData || !Array.isArray((chartData as { datasets?: unknown[] }).datasets)) {
    return (
      <div className="flex items-center justify-center h-full text-ash text-sm">
        Chart data unavailable
      </div>
    )
  }
  switch (chart.chart_type) {
    case 'line':
      return <Line data={chartData as any} options={options as ChartOptions<'line'>} />
    case 'bar':
      return <Bar data={chartData as any} options={options} />
    case 'pie':
      return <Pie data={chartData as any} options={options as ChartOptions<'pie'>} />
    case 'doughnut':
      return <Doughnut data={chartData as any} options={options as ChartOptions<'doughnut'>} />
    case 'scatter':
      return <Scatter data={chartData as any} options={options as ChartOptions<'scatter'>} />
    default:
      return (
        <div className="flex items-center justify-center h-full text-ash text-sm">
          Unsupported type: {chart.chart_type}
        </div>
      )
  }
}
