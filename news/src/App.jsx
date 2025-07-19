import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import './App.css';

// Mock data structure
const goldStandardResponse = {
  credibilityScore: 85,
  supportingFacts: [
    { title: "RBI Keeps Repo Rate Unchanged", url: "https://example.com", sourceName: "Reuters" },
    { title: "Indian Central Bank Holds Rate", url: "https://example.com", sourceName: "Bloomberg" },
    { title: "RBI Policy: Rate Steady at 6.5%", url: "https://example.com", sourceName: "India Today" },
  ],
  analysis: {
    extractedKeywords: ["RBI", "Inflation", "Repo Rate", "Economic Growth"],
    sentiment: { tone: "Neutral", score: 0.92 },
    source: { domain: "indiatimes.com", reliability: "Generally Reliable" }
  }
};

function App() {
  const [urlInput, setUrlInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState(null);
  // Newspaper theme: use serif font, off-white bg, black text

  const handleAnalyze = () => {
    if (!urlInput) return;
    setIsLoading(true);
    setResults(null);
    setTimeout(() => {
      setResults(goldStandardResponse);
      setIsLoading(false);
    }, 2500);
  };

  return (
    <main className="min-h-screen bg-[#faf7f2] text-black font-serif p-4">
      <div className="max-w-3xl mx-auto shadow-xl border border-gray-300 bg-white rounded-lg p-6 newspaper-paper">
        {/* Masthead */}
        <div className="border-b-4 border-black pb-2 mb-8 text-center">
          <h1 className="text-5xl font-extrabold tracking-wide uppercase font-serif">The Veracity Times</h1>
          <p className="italic text-lg text-gray-700 mt-1 font-serif">Your trusted source for news analysis</p>
        </div>
        {/* Header */}
        <motion.header 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-10"
        >
          <h2 className="text-3xl md:text-4xl font-bold font-serif mb-2">News Veracity Detector</h2>
          <p className="text-gray-600 mt-2 font-serif">
            Your AI co-pilot for navigating the complex world of online news
          </p>
        </motion.header>
        {/* Input Section */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-10"
        >
          <div className="flex gap-4">
            <input
              type="url"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Paste a news article URL..."
              className="input-field border border-gray-400 bg-[#f5f5f5] text-black font-serif"
            />
            <button
              onClick={handleAnalyze}
              disabled={isLoading || !urlInput}
              className="button-primary bg-black text-white font-serif border border-gray-700 hover:bg-gray-800"
            >
              {isLoading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
        </motion.div>
        {/* Results Section */}
        <AnimatePresence>
          {isLoading && <LoadingSpinner />}
          {results && <ResultsDisplay data={results} />}
        </AnimatePresence>
      </div>
    </main>
  );
}

const LoadingSpinner = () => (
  <motion.div
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    className="text-center p-8"
  >
    <div className="h-12 w-12 border-4 border-t-cyan-400 border-r-cyan-400 border-b-gray-600 border-l-gray-600 rounded-full animate-spin mx-auto"/>
    <p className="mt-4 text-gray-400">Analyzing article...</p>
  </motion.div>
);

const ResultsDisplay = ({ data }) => {
  const scoreColor = data.credibilityScore > 70 ? '#4ade80' : 
                     data.credibilityScore > 40 ? '#facc15' : '#f87171';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border-2 border-gray-400 rounded-xl p-8 shadow-lg font-serif"
    >
      <div className="grid md:grid-cols-3 gap-8 mb-8">
        <ScoreCircle score={data.credibilityScore} color={scoreColor} />
        <div className="md:col-span-2 space-y-6">
          <AnalysisMetrics 
            reliability={data.analysis.source.reliability}
            tone={data.analysis.sentiment.tone}
          />
          <KeywordList keywords={data.analysis.extractedKeywords} />
        </div>
      </div>
      <hr className="border-t-2 border-gray-300 my-6" />
      <CorroborationList facts={data.supportingFacts} />
    </motion.div>
  );
};

const ScoreCircle = ({ score, color }) => (
  <div className="relative h-48 w-48 mx-auto">
    <svg className="transform -rotate-90" viewBox="0 0 100 100">
      <circle cx="50" cy="50" r="45" fill="none" stroke="#374151" strokeWidth="10"/>
      <motion.circle
        cx="50"
        cy="50"
        r="45"
        fill="none"
        stroke={color}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={2 * Math.PI * 45}
        initial={{ strokeDashoffset: 2 * Math.PI * 45 }}
        animate={{ strokeDashoffset: 2 * Math.PI * 45 * (1 - score / 100) }}
        transition={{ duration: 1.5, ease: "easeOut" }}
      />
    </svg>
    <div className="absolute inset-0 flex items-center justify-center">
      <span className="text-4xl font-bold" style={{ color }}>{score}</span>
      <span className="text-xl" style={{ color }}>%</span>
    </div>
  </div>
);

const AnalysisMetrics = ({ reliability, tone }) => (
  <div className="grid grid-cols-2 gap-4 bg-gray-100 rounded-lg p-4 border border-gray-300">
    <div className="text-center">
      <p className="text-sm text-gray-500">Source Grade</p>
      <p className="text-lg font-bold text-blue-900 font-serif">{reliability}</p>
    </div>
    <div className="text-center">
      <p className="text-sm text-gray-500">Article Tone</p>
      <p className="text-lg font-bold text-blue-900 font-serif">{tone}</p>
    </div>
  </div>
);

const KeywordList = ({ keywords }) => (
  <div>
    <p className="text-sm text-gray-500 mb-2">Keywords Detected</p>
    <div className="flex flex-wrap gap-2">
      {keywords.map(keyword => (
        <span 
          key={keyword}
          className="bg-gray-200 text-gray-800 text-sm px-3 py-1 rounded-full font-serif border border-gray-300"
        >
          {keyword}
        </span>
      ))}
    </div>
  </div>
);

const CorroborationList = ({ facts }) => (
  <div className="pt-2">
    <h3 className="text-2xl font-extrabold mb-4 font-serif border-b border-gray-300 pb-2">Corroboration Network</h3>
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        visible: { transition: { staggerChildren: 0.1 } }
      }}
    >
      {facts.map((fact, index) => (
        <motion.div
          key={index}
          variants={{
            hidden: { opacity: 0, x: -20 },
            visible: { opacity: 1, x: 0 }
          }}
          className="bg-white border border-gray-300 p-4 rounded-lg mb-4 shadow-sm font-serif text-left hover:shadow-md transition"
        >
          <a href={fact.url} target="_blank" rel="noopener noreferrer">
            <h4 className="font-bold text-blue-800 text-lg mb-1 font-serif hover:underline">{fact.title}</h4>
            <p className="text-sm text-gray-600 font-serif">{fact.sourceName}</p>
          </a>
        </motion.div>
      ))}
    </motion.div>
  </div>
);

export default App;
