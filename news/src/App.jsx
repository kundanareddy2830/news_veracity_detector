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
  const [inputMode, setInputMode] = useState('url'); // 'url' or 'text'
  const [urlInput, setUrlInput] = useState('');
  const [textInput, setTextInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [results, setResults] = useState(null);
  // Newspaper theme: use serif font, off-white bg, black text

  const handleAnalyze = () => {
    if ((inputMode === 'url' && !urlInput) || (inputMode === 'text' && !textInput)) return;
    setIsLoading(true);
    setResults(null);
    setTimeout(() => {
      setResults(goldStandardResponse);
      setIsLoading(false);
    }, 2500);
  };

  // Get today's date for edition line
  const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

  return (
    <main className="min-h-screen bg-[#faf7f2] text-black font-serif p-4 md:p-8 lg:p-12 relative">
      {/* Torn top edge for realism on the background card */}
      <img src="/torn-top.png" alt="torn edge" style={{position:'absolute', top:0, left:0, width:'100%', zIndex:3, pointerEvents:'none'}} />
      <div className="max-w-4xl mx-auto shadow-xl border border-gray-300 rounded-lg p-8 sm:p-12 newspaper-paper relative overflow-hidden" style={{background:'rgba(220,220,220,0.45)'}}>
        {/* Dog-ear crease for realism */}
        <div className="dog-ear-crease"></div>
        {/* Watermark */}
        <div className="newspaper-watermark">NEWS</div>
        {/* Masthead */}
        <div className="border-b-4 border-black pb-2 mb-2 text-center newspaper-masthead relative z-10 flex flex-col items-center">
            <span className="newspaper-crest">EST. 2024</span>
            <h1 className="text-5xl font-extrabold tracking-wide uppercase newspaper-masthead">THE VERACITY TIMES</h1>
            <div className="newspaper-edition">Published: {today} | Edition No. 1</div>
            <p className="italic text-lg text-gray-700 mt-1 font-serif">Your trusted source for news analysis</p>
          </div>
          {/* Input Mode Toggle */}
          <div className="flex flex-col items-center gap-2 mb-6 mt-4">
            <span className="font-semibold text-gray-700">Analyze Article From:</span>
            <div className="flex gap-2">
              <button
                className={`px-4 py-2 rounded-t-lg border-b-2 font-semibold transition-colors duration-150 ${inputMode === 'url' ? 'border-black bg-gray-100' : 'border-transparent bg-gray-200 text-gray-500'}`}
                onClick={() => setInputMode('url')}
              >
                URL
              </button>
              <button
                className={`px-4 py-2 rounded-t-lg border-b-2 font-semibold transition-colors duration-150 ${inputMode === 'text' ? 'border-black bg-gray-100' : 'border-transparent bg-gray-200 text-gray-500'}`}
                onClick={() => setInputMode('text')}
              >
                Text
              </button>
            </div>
          </div>
          {/* Input Section */}
          <div className="mb-10">
            {inputMode === 'url' ? (
              <div className="flex gap-4">
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  placeholder="Paste a news article URL..."
                  className="input-field border border-gray-400 bg-[#f5f5f5] text-black font-serif flex-1"
                />
                <button
                  onClick={handleAnalyze}
                  disabled={isLoading || !urlInput}
                  className="button-primary bg-black text-white font-serif border border-gray-700 hover:bg-gray-800"
                >
                  {isLoading ? 'Analyzing...' : 'Analyze'}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-4">
                <textarea
                  value={textInput}
                  onChange={(e) => setTextInput(e.target.value)}
                  placeholder="Paste or type news article text..."
                  className="input-field border border-gray-400 bg-[#f5f5f5] text-black font-serif min-h-[100px] resize-vertical"
                />
                <button
                  onClick={handleAnalyze}
                  disabled={isLoading || !textInput}
                  className="self-end button-primary bg-black text-white font-serif border border-gray-700 hover:bg-gray-800"
                >
                  {isLoading ? 'Analyzing...' : 'Analyze'}
                </button>
              </div>
            )}
          </div>
          {/* Results Section */}
          <AnimatePresence>
            {(isLoading || results !== null) && (
              <ResultsDisplay data={results} isLoading={isLoading} />
            )}
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

const ResultsDisplay = ({ data, isLoading }) => {
  const scoreColor = data?.credibilityScore > 70 ? '#4ade80' : 
                     data?.credibilityScore > 40 ? '#facc15' : '#f87171';
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border-2 border-gray-300 rounded-xl p-8 sm:p-12 shadow-lg font-serif relative z-10 min-h-[520px] flex flex-col justify-center items-center"
    >
      {isLoading ? (
        <div className="flex flex-col items-center justify-center min-h-[400px] w-full">
          <LoadingSpinner />
        </div>
      ) : data ? (
        <>
          <div className="results-columns mb-10 space-y-10 w-full">
            <ScoreCircle score={data.credibilityScore} color={scoreColor} />
            <div className="md:col-span-2 space-y-10">
              <AnalysisMetrics 
                reliability={data.analysis.source.reliability}
                tone={data.analysis.sentiment.tone}
              />
              <KeywordList keywords={data.analysis.extractedKeywords} />
            </div>
          </div>
          <CorroborationList facts={data.supportingFacts} />
        </>
      ) : null}
    </motion.div>
  );
};

const ScoreCircle = ({ score, color }) => {
  // Animate the score number
  const [displayScore, setDisplayScore] = useState(0);
  React.useEffect(() => {
    let start = 0;
    const duration = 1200;
    const startTime = performance.now();
    function animate(now) {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      setDisplayScore(Math.floor(progress * score));
      if (progress < 1) requestAnimationFrame(animate);
      else setDisplayScore(score);
    }
    animate(startTime);
  }, [score]);
  const circumference = 2 * Math.PI * 45;
  const progress = displayScore / 100;
  return (
    <div className="relative h-56 w-56 mx-auto flex flex-col items-center justify-center">
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
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - progress)}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: circumference * (1 - progress) }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="flex items-end justify-center">
          <span className="text-6xl font-extrabold drop-shadow-md" style={{ color }}>{displayScore}</span>
          <span className="text-2xl font-bold mb-1 ml-1" style={{ color }}>%</span>
        </div>
        <span className="text-base font-semibold text-gray-700 mt-1 tracking-wide" style={{textShadow:'0 1px 4px rgba(0,0,0,0.08)'}}>Credibility</span>
      </div>
    </div>
  );
};

const AnalysisMetrics = ({ reliability, tone }) => (
  <div className="grid grid-cols-2 gap-4 bg-gray-50 rounded-lg p-4">
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
    <h3 className="section-heading mb-4 border-b border-gray-300 pb-2">Corroboration Network</h3>
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        visible: { transition: { staggerChildren: 0.13 } }
      }}
    >
      {facts.map((fact, index) => (
        <motion.div
          key={index}
          variants={{
            hidden: { opacity: 0, x: -20 },
            visible: { opacity: 1, x: 0 }
          }}
          initial="hidden"
          animate="visible"
          transition={{ duration: 0.5, delay: 0.13 * index }}
          className="bg-gray-50 p-4 rounded-lg mb-4 font-serif text-left card-hover"
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
