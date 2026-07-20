import { useState, useEffect } from 'react'
import { Smartphone, Zap, CheckCircle, XCircle, Clock, Loader2, Download } from 'lucide-react'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [prompt, setPrompt] = useState('')
  const [packageName, setPackageName] = useState('')
  const [deliverables, setDeliverables] = useState(['aab', 'apk'])
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [jobs, setJobs] = useState([])
  const [selectedJob, setSelectedJob] = useState(null)

  useEffect(() => {
    fetchJobs()
  }, [])

  useEffect(() => {
    if (selectedJob && selectedJob.status !== 'succeeded' && selectedJob.status !== 'failed') {
      const interval = setInterval(() => {
        fetchJobStatus(selectedJob.job_id)
      }, 2000)
      return () => clearInterval(interval)
    }
  }, [selectedJob])

  const fetchJobs = async () => {
    try {
      const response = await fetch(`${API_URL}/v1/jobs?limit=10`)
      const data = await response.json()
      setJobs(data)
    } catch (error) {
      console.error('Failed to fetch jobs:', error)
    }
  }

  const fetchJobStatus = async (jobId) => {
    try {
      const response = await fetch(`${API_URL}/v1/jobs/${jobId}`)
      const data = await response.json()
      setSelectedJob(data)

      setJobs(prev => prev.map(j =>
        j.job_id === jobId ? { ...j, status: data.status } : j
      ))
    } catch (error) {
      console.error('Failed to fetch job status:', error)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)

    try {
      const response = await fetch(`${API_URL}/v1/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nl_prompt: prompt,
          package_name: packageName,
          deliverables: deliverables,
          signing_profile: 'prod-default'
        })
      })

      if (!response.ok) throw new Error('Failed to create job')

      const data = await response.json()

      await fetchJobStatus(data.job_id)
      await fetchJobs()

      setPrompt('')
      setPackageName('')
    } catch (error) {
      alert(`Error: ${error.message}`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const getStatusColor = (status) => {
    const colors = {
      'pending': 'text-gray-500',
      'spec_generating': 'text-blue-500',
      'spec_generated': 'text-blue-600',
      'codegen': 'text-purple-500',
      'building': 'text-yellow-500',
      'signing': 'text-orange-500',
      'succeeded': 'text-green-500',
      'failed': 'text-red-500'
    }
    return colors[status] || 'text-gray-500'
  }

  const getStatusIcon = (status) => {
    if (status === 'succeeded') return <CheckCircle className="w-5 h-5" />
    if (status === 'failed') return <XCircle className="w-5 h-5" />
    if (status === 'pending') return <Clock className="w-5 h-5" />
    return <Loader2 className="w-5 h-5 animate-spin" />
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Smartphone className="w-12 h-12 text-purple-400" />
            <h1 className="text-5xl font-bold text-white">NL2Build Cloud</h1>
          </div>
          <p className="text-xl text-purple-200">
            Transform natural language into production-ready Android apps
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8">
          <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 shadow-2xl border border-white/20">
            <h2 className="text-2xl font-bold text-white mb-6 flex items-center gap-2">
              <Zap className="w-6 h-6 text-yellow-400" />
              Create New App
            </h2>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-purple-200 mb-2">
                  Describe Your App
                </label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="An app with a mic button that captures speech and displays it as text"
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 min-h-[120px]"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-purple-200 mb-2">
                  Package Name
                </label>
                <input
                  type="text"
                  value={packageName}
                  onChange={(e) => setPackageName(e.target.value)}
                  placeholder="com.example.myapp"
                  pattern="^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$"
                  className="w-full px-4 py-3 bg-white/5 border border-white/20 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-purple-200 mb-2">
                  Deliverables
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 text-white">
                    <input
                      type="checkbox"
                      checked={deliverables.includes('aab')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setDeliverables([...deliverables, 'aab'])
                        } else {
                          setDeliverables(deliverables.filter(d => d !== 'aab'))
                        }
                      }}
                      className="w-4 h-4"
                    />
                    AAB (Play Store)
                  </label>
                  <label className="flex items-center gap-2 text-white">
                    <input
                      type="checkbox"
                      checked={deliverables.includes('apk')}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setDeliverables([...deliverables, 'apk'])
                        } else {
                          setDeliverables(deliverables.filter(d => d !== 'apk'))
                        }
                      }}
                      className="w-4 h-4"
                    />
                    APK (Direct Install)
                  </label>
                </div>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-gradient-to-r from-purple-600 to-pink-600 text-white py-4 rounded-lg font-semibold hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Creating Build...
                  </>
                ) : (
                  <>
                    <Zap className="w-5 h-5" />
                    Start Build
                  </>
                )}
              </button>
            </form>
          </div>

          <div className="space-y-6">
            {selectedJob && (
              <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 shadow-2xl border border-white/20">
                <h3 className="text-xl font-bold text-white mb-4">
                  Job: {selectedJob.job_id}
                </h3>

                <div className="space-y-4">
                  <div className={`flex items-center gap-3 ${getStatusColor(selectedJob.status)}`}>
                    {getStatusIcon(selectedJob.status)}
                    <span className="font-semibold capitalize">
                      {selectedJob.status.replace('_', ' ')}
                    </span>
                  </div>

                  {selectedJob.current_step && (
                    <div className="text-sm text-purple-200">
                      Step: <span className="font-mono">{selectedJob.current_step}</span>
                    </div>
                  )}

                  {selectedJob.errors && (
                    <div className="bg-red-500/20 border border-red-500/50 rounded-lg p-4 text-red-200 text-sm">
                      {selectedJob.errors}
                    </div>
                  )}

                  {selectedJob.artifacts && selectedJob.artifacts.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="font-semibold text-white">Download Artifacts:</h4>
                      {selectedJob.artifacts.map((artifact, idx) => (
                        <a
                          key={idx}
                          href={artifact.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 bg-green-500/20 border border-green-500/50 rounded-lg p-3 text-green-200 hover:bg-green-500/30 transition-colors"
                        >
                          <Download className="w-4 h-4" />
                          <span className="font-mono text-sm">{artifact.type.toUpperCase()}</span>
                          <span className="text-xs ml-auto">
                            {artifact.sha256.substring(0, 8)}...
                          </span>
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="bg-white/10 backdrop-blur-lg rounded-2xl p-8 shadow-2xl border border-white/20">
              <h3 className="text-xl font-bold text-white mb-4">Recent Builds</h3>

              <div className="space-y-3">
                {jobs.length === 0 ? (
                  <p className="text-purple-200 text-sm">No builds yet</p>
                ) : (
                  jobs.map((job) => (
                    <button
                      key={job.job_id}
                      onClick={() => fetchJobStatus(job.job_id)}
                      className="w-full text-left bg-white/5 hover:bg-white/10 rounded-lg p-4 transition-colors border border-white/10"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-mono text-sm text-purple-300">
                            {job.job_id}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            {job.package_name}
                          </div>
                        </div>
                        <div className={`flex items-center gap-2 ${getStatusColor(job.status)}`}>
                          {getStatusIcon(job.status)}
                        </div>
                      </div>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
