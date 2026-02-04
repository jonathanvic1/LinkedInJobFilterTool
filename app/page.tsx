export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-900 text-gray-100 p-8">
      <div className="max-w-2xl text-center space-y-6">
        <div className="flex items-center justify-center space-x-2 mb-4">
          <div className="flex items-center bg-gray-800 px-3 py-2 rounded-lg border border-gray-700">
            <span className="text-2xl font-bold text-blue-400">Job Filter Tool</span>
          </div>
        </div>
        <p className="text-gray-400">
          Multi-Platform Job Automation for LinkedIn and Indeed
        </p>
        <div className="pt-4">
          <p className="text-sm text-gray-500">
            This application requires a Python backend to run. Please refer to the documentation for setup instructions.
          </p>
        </div>
      </div>
    </main>
  )
}
