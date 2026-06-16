import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface ChartDataPoint {
  month: string
  tokens: number
}

interface UsageChartProps {
  data: ChartDataPoint[]
}

export default function UsageChart({ data }: UsageChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
        <XAxis dataKey="month" tick={{ fontSize: 12 }} />
        <YAxis tick={{ fontSize: 12 }} />
        <Tooltip formatter={(val: number) => val.toLocaleString()} />
        <Legend />
        <Bar dataKey="tokens" fill="#1D9E75" name="Tokens used" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
