import { Link } from 'react-router-dom'

function FactorCard({ factor }) {
  const categoryColors = {
    sec: 'bg-blue-100 text-blue-800',
    macro: 'bg-green-100 text-green-800',
    aviation: 'bg-purple-100 text-purple-800',
    energy: 'bg-yellow-100 text-yellow-800',
    patents: 'bg-pink-100 text-pink-800',
    environmental: 'bg-teal-100 text-teal-800',
    weather: 'bg-cyan-100 text-cyan-800',
    trends: 'bg-orange-100 text-orange-800',
    sentiment: 'bg-red-100 text-red-800',
    shipping: 'bg-indigo-100 text-indigo-800',
    github: 'bg-gray-100 text-gray-800',
    satellite: 'bg-emerald-100 text-emerald-800',
  }

  const colorClass = categoryColors[factor.category] || 'bg-gray-100 text-gray-800'

  return (
    <Link
      to={`/factors/${factor.id}`}
      className="block bg-white rounded-lg shadow hover:shadow-md transition-shadow p-6"
    >
      <div className="flex justify-between items-start">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">{factor.name}</h3>
          <p className="mt-1 text-sm text-gray-500 line-clamp-2">
            {factor.description || 'No description available'}
          </p>
        </div>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${colorClass}`}>
          {factor.category}
        </span>
      </div>
      <div className="mt-4 flex items-center text-sm text-gray-500">
        <span>Frequency: {factor.frequency}</span>
      </div>
    </Link>
  )
}

export default FactorCard
