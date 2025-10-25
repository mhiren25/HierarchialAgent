import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Clock, Database, BookOpen, FileText, Loader2, Trash2, MessageSquare, Activity, Zap, CheckCircle, AlertCircle } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

// Agent Communication Component
const AgentCommunication = ({ agentPath, currentAgent, isProcessing }) => {
  const agents = [
    { name: 'supervisor', label: 'Supervisor', icon: Bot, color: 'purple' },
    { name: 'log_team', label: 'Log Team', icon: FileText, color: 'orange' },
    { name: 'knowledge_team', label: 'Knowledge', icon: BookOpen, color: 'blue' },
    { name: 'db_team', label: 'Database', icon: Database, color: 'green' },
  ];

  const getAgentColor = (name) => {
    const colors = {
      supervisor: 'bg-purple-500',
      log_team: 'bg-orange-500',
      knowledge_team: 'bg-blue-500',
      db_team: 'bg-green-500',
    };
    return colors[name] || 'bg-gray-500';
  };

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Activity className="w-5 h-5 text-purple-600" />
        <h3 className="font-semibold text-slate-800">Agent Communication</h3>
      </div>

      {/* Agent Flow Visualization */}
      <div className="flex items-center justify-between mb-6">
        {agents.map((agent, idx) => {
          const isActive = currentAgent === agent.name;
          const hasVisited = agentPath.includes(agent.name);
          const Icon = agent.icon;

          return (
            <React.Fragment key={agent.name}>
              <div className="flex flex-col items-center gap-2">
                <div className={`relative w-12 h-12 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isActive 
                    ? `${getAgentColor(agent.name)} shadow-glow scale-110` 
                    : hasVisited 
                    ? `${getAgentColor(agent.name)} opacity-60` 
                    : 'bg-slate-200'
                }`}>
                  <Icon className={`w-6 h-6 ${isActive || hasVisited ? 'text-white' : 'text-slate-400'}`} />
                  {isActive && (
                    <div className="absolute inset-0 rounded-full border-2 border-white pulse-ring"></div>
                  )}
                  {hasVisited && !isActive && (
                    <CheckCircle className="absolute -bottom-1 -right-1 w-4 h-4 text-green-500 bg-white rounded-full" />
                  )}
                </div>
                <span className={`text-xs font-medium ${
                  isActive ? 'text-slate-900' : hasVisited ? 'text-slate-600' : 'text-slate-400'
                }`}>
                  {agent.label}
                </span>
                {isActive && isProcessing && (
                  <div className="flex gap-1 mt-1">
                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full agent-thinking"></span>
                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full agent-thinking" style={{ animationDelay: '0.2s' }}></span>
                    <span className="w-1.5 h-1.5 bg-purple-500 rounded-full agent-thinking" style={{ animationDelay: '0.4s' }}></span>
                  </div>
                )}
              </div>
              {idx < agents.length - 1 && (
                <div className={`flex-1 h-0.5 transition-all duration-500 ${
                  agentPath.length > 0 && agentPath.indexOf(agents[idx + 1].name) > agentPath.indexOf(agent.name)
                    ? 'bg-gradient-to-r from-purple-500 to-blue-500'
                    : 'bg-slate-200'
                }`}></div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Agent Activity Log */}
      {agentPath.length > 0 && (
        <div className="space-y-2 max-h-32 overflow-y-auto custom-scrollbar">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Activity Log</p>
          {agentPath.map((agent, idx) => {
            const agentInfo = agents.find(a => a.name === agent);
            const Icon = agentInfo?.icon || Bot;
            return (
              <div key={idx} className="flex items-center gap-2 text-sm animate-slide-up">
                <div className={`w-2 h-2 rounded-full ${getAgentColor(agent)}`}></div>
                <Icon className="w-4 h-4 text-slate-400" />
                <span className="text-slate-600">{agentInfo?.label || agent}</span>
                <span className="text-xs text-slate-400 ml-auto">Step {idx + 1}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

// Live Streaming Message Component
const StreamingMessage = ({ content, agentName }) => {
  const [displayedContent, setDisplayedContent] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    if (currentIndex < content.length) {
      const timeout = setTimeout(() => {
        setDisplayedContent(prev => prev + content[currentIndex]);
        setCurrentIndex(prev => prev + 1);
      }, 20);
      return () => clearTimeout(timeout);
    }
  }, [currentIndex, content]);

  return (
    <div className="animate-fade-in">
      <div className="prose prose-sm max-w-none">
        {displayedContent}
        {currentIndex < content.length && (
          <span className="inline-block w-2 h-4 bg-blue-500 ml-1 animate-pulse"></span>
        )}
      </div>
    </div>
  );
};

export default function LangGraphChatApp() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [agentPath, setAgentPath] = useState([]);
  const [currentAgent, setCurrentAgent] = useState(null);
  const [activeThreads, setActiveThreads] = useState([]);
  const [liveAgentUpdates, setLiveAgentUpdates] = useState([]);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  useEffect(() => {
    loadThreads();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, liveAgentUpdates]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const loadThreads = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/threads`);
      const data = await response.json();
      setActiveThreads(data.threads || []);
    } catch (error) {
      console.error('Error loading threads:', error);
    }
  };

  const loadThread = async (tid) => {
    try {
      const response = await fetch(`${API_BASE_URL}/threads/${tid}`);
      const data = await response.json();
      
      const formattedMessages = [];
      data.messages.forEach(msg => {
        formattedMessages.push({
          role: 'user',
          content: msg.user,
          timestamp: msg.timestamp
        });
        formattedMessages.push({
          role: 'assistant',
          content: msg.assistant,
          timestamp: msg.timestamp
        });
      });
      
      setMessages(formattedMessages);
      setThreadId(tid);
      setAgentPath([]);
      setLiveAgentUpdates([]);
    } catch (error) {
      console.error('Error loading thread:', error);
    }
  };

  const sendMessageWithWebSocket = (message, tid) => {
    const wsUrl = `ws://localhost:8000/ws/${tid}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    setLiveAgentUpdates([]);
    setAgentPath([]);

    ws.onopen = () => {
      ws.send(JSON.stringify({ message }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'agent_update') {
        setCurrentAgent(data.agent);
        setAgentPath(prev => {
          if (!prev.includes(data.agent)) {
            return [...prev, data.agent];
          }
          return prev;
        });
        setLiveAgentUpdates(prev => [...prev, {
          type: 'agent',
          agent: data.agent,
          timestamp: data.timestamp
        }]);
      } else if (data.type === 'message_chunk') {
        setLiveAgentUpdates(prev => [...prev, {
          type: 'message',
          content: data.content,
          agent: data.agent,
          timestamp: Date.now()
        }]);
      } else if (data.type === 'complete') {
        setCurrentAgent(null);
        setIsLoading(false);
        // Collect all message chunks
        const messageChunks = liveAgentUpdates
          .filter(u => u.type === 'message')
          .map(u => u.content);
        
        if (messageChunks.length > 0) {
          const fullMessage = messageChunks[messageChunks.length - 1];
          const assistantMessage = {
            role: 'assistant',
            content: fullMessage,
            timestamp: new Date().toISOString(),
            agentPath: data.agent_path
          };
          setMessages(prev => [...prev, assistantMessage]);
          setAgentPath(data.agent_path);
        }
        loadThreads();
      } else if (data.type === 'error') {
        console.error('WebSocket error:', data.error);
        setIsLoading(false);
        setCurrentAgent(null);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setIsLoading(false);
      setCurrentAgent(null);
    };

    ws.onclose = () => {
      setCurrentAgent(null);
    };
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    const messageToSend = inputValue;
    setInputValue('');
    setIsLoading(true);
    setAgentPath([]);
    setLiveAgentUpdates([]);

    const tid = threadId || `thread_${Date.now()}`;
    setThreadId(tid);

    // Try WebSocket first, fallback to HTTP
    try {
      sendMessageWithWebSocket(messageToSend, tid);
    } catch (error) {
      console.log('WebSocket failed, using HTTP fallback');
      // HTTP fallback
      try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: messageToSend,
            thread_id: tid
          })
        });

        const data = await response.json();
        const assistantMessage = {
          role: 'assistant',
          content: data.response,
          timestamp: data.metadata.timestamp,
          agentPath: data.agent_path
        };

        setMessages(prev => [...prev, assistantMessage]);
        setThreadId(data.thread_id);
        setAgentPath(data.agent_path);
        loadThreads();
      } catch (httpError) {
        console.error('Error sending message:', httpError);
        const errorMessage = {
          role: 'assistant',
          content: 'Sorry, there was an error processing your request. Please try again.',
          timestamp: new Date().toISOString(),
          isError: true
        };
        setMessages(prev => [...prev, errorMessage]);
      } finally {
        setIsLoading(false);
      }
    }
  };

  const deleteThread = async (tid) => {
    try {
      await fetch(`${API_BASE_URL}/threads/${tid}`, { method: 'DELETE' });
      
      if (tid === threadId) {
        setMessages([]);
        setThreadId(null);
        setAgentPath([]);
        setLiveAgentUpdates([]);
      }
      
      loadThreads();
    } catch (error) {
      console.error('Error deleting thread:', error);
    }
  };

  const newConversation = () => {
    setMessages([]);
    setThreadId(null);
    setAgentPath([]);
    setLiveAgentUpdates([]);
    if (wsRef.current) {
      wsRef.current.close();
    }
  };

  const getAgentIcon = (agent) => {
    const icons = {
      log_team: FileText,
      knowledge_team: BookOpen,
      db_team: Database,
      supervisor: Bot
    };
    const Icon = icons[agent] || Bot;
    return <Icon className="w-4 h-4" />;
  };

  const getAgentColor = (agent) => {
    const colors = {
      log_team: 'bg-orange-100 text-orange-700 border-orange-200',
      knowledge_team: 'bg-blue-100 text-blue-700 border-blue-200',
      db_team: 'bg-green-100 text-green-700 border-green-200',
      supervisor: 'bg-purple-100 text-purple-700 border-purple-200'
    };
    return colors[agent] || 'bg-gray-100 text-gray-700 border-gray-200';
  };

  const formatContent = (content) => {
    return content.split('\n').map((line, i) => {
      if (line.startsWith('# ')) {
        return <h1 key={i} className="text-xl font-bold mt-4 mb-2">{line.substring(2)}</h1>;
      }
      if (line.startsWith('## ')) {
        return <h2 key={i} className="text-lg font-bold mt-3 mb-2">{line.substring(3)}</h2>;
      }
      if (line.startsWith('### ')) {
        return <h3 key={i} className="text-base font-bold mt-2 mb-1">{line.substring(4)}</h3>;
      }
      if (line.startsWith('- ')) {
        return <li key={i} className="ml-4">{line.substring(2)}</li>;
      }
      if (line.startsWith('**') && line.endsWith('**')) {
        return <p key={i} className="font-bold my-1">{line.slice(2, -2)}</p>;
      }
      if (line.trim() === '') {
        return <div key={i} className="h-2" />;
      }
      return <p key={i} className="my-1">{line}</p>;
    });
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      {/* Sidebar */}
      <div className="w-80 bg-white border-r border-slate-200 flex flex-col shadow-xl">
        <div className="p-6 border-b border-slate-200 bg-gradient-to-r from-blue-600 to-purple-600">
          <h1 className="text-2xl font-bold text-white mb-2">
            LangGraph Teams
          </h1>
          <p className="text-sm text-blue-100">
            Hierarchical Agent System
          </p>
        </div>

        <div className="p-4">
          <button
            onClick={newConversation}
            className="w-full bg-gradient-to-r from-blue-500 to-blue-600 text-white px-4 py-3 rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 font-medium"
          >
            <MessageSquare className="w-5 h-5" />
            New Conversation
          </button>
        </div>

        {/* Threads List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Recent Conversations
          </h2>
          {activeThreads.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-8">No conversations yet</p>
          ) : (
            activeThreads.map((thread) => (
              <div
                key={thread.thread_id}
                className={`p-3 rounded-lg border cursor-pointer transition-all group flex items-center justify-between ${
                  threadId === thread.thread_id
                    ? 'bg-blue-50 border-blue-200 shadow-sm'
                    : 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-sm'
                }`}
              >
                <div
                  onClick={() => loadThread(thread.thread_id)}
                  className="flex-1"
                >
                  <p className="text-sm font-medium text-slate-800 truncate">
                    {thread.thread_id}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <MessageSquare className="w-3 h-3 text-slate-400" />
                    <p className="text-xs text-slate-500">
                      {thread.message_count} messages
                    </p>
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteThread(thread.thread_id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-100 rounded transition-all"
                >
                  <Trash2 className="w-4 h-4 text-red-600" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Agent Path Display */}
        {(agentPath.length > 0 || isLoading) && (
          <div className="p-4 bg-gradient-to-r from-slate-50 to-blue-50 border-t border-slate-200">
            <h3 className="text-xs font-semibold text-slate-600 mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-purple-600" />
              Execution Path
            </h3>
            <div className="flex flex-wrap gap-2">
              {agentPath.map((agent, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border shadow-sm animate-slide-in-right ${getAgentColor(agent)}`}
                  style={{ animationDelay: `${idx * 0.1}s` }}
                >
                  {getAgentIcon(agent)}
                  <span>{agent.replace('_', ' ')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-slate-200 px-6 py-4 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                <Bot className="w-7 h-7 text-white" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">
                  Hierarchical Agent Assistant
                </h2>
                <p className="text-sm text-slate-500 flex items-center gap-2">
                  <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                  Online • Log Analysis • Knowledge Base • Database Queries
                </p>
              </div>
            </div>
            {isLoading && (
              <div className="flex items-center gap-2 text-sm text-slate-600">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                <span>Processing...</span>
              </div>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {messages.length === 0 && !isLoading && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-2xl animate-fade-in">
                <div className="w-24 h-24 bg-gradient-to-br from-blue-100 via-purple-100 to-pink-100 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-xl">
                  <Bot className="w-12 h-12 text-blue-600" />
                </div>
                <h3 className="text-3xl font-bold gradient-text mb-3">
                  Welcome to LangGraph Teams
                </h3>
                <p className="text-slate-600 mb-8 text-lg">
                  Ask me to analyze logs, search documentation, or query the database.
                </p>
                <div className="grid grid-cols-3 gap-4 text-left">
                  {[
                    { icon: FileText, color: 'orange', title: 'Log Analysis', desc: 'Compare orders and find failures' },
                    { icon: BookOpen, color: 'blue', title: 'Knowledge Base', desc: 'Search docs and guides' },
                    { icon: Database, color: 'green', title: 'Database', desc: 'Query data with natural language' }
                  ].map(({ icon: Icon, color, title, desc }) => (
                    <div key={title} className={`p-5 bg-${color}-50 border border-${color}-200 rounded-xl hover:shadow-lg transition-all cursor-pointer`}>
                      <Icon className={`w-7 h-7 text-${color}-600 mb-3`} />
                      <h4 className="font-semibold text-sm text-slate-800 mb-1">{title}</h4>
                      <p className="text-xs text-slate-600">{desc}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-8 text-sm text-slate-500 bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <p className="font-semibold mb-2">💡 Try these examples:</p>
                  <p className="text-xs">"Compare orders GOOD001 and BAD001"</p>
                  <p className="text-xs">"What causes payment failures?"</p>
                  <p className="text-xs">"Show me all failed orders from yesterday"</p>
                </div>
              </div>
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex gap-4 message-arrive ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg">
                  <Bot className="w-6 h-6 text-white" />
                </div>
              )}
              
              <div
                className={`max-w-3xl ${
                  message.role === 'user'
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg'
                    : message.isError
                    ? 'bg-red-50 border-2 border-red-200 text-red-800'
                    : 'bg-white border border-slate-200 text-slate-800 shadow-sm'
                } rounded-2xl px-6 py-4`}
              >
                <div className="prose prose-sm max-w-none">
                  {formatContent(message.content)}
                </div>
                
                {message.agentPath && message.agentPath.length > 0 && (
                  <div className="mt-4 pt-4 border-t border-slate-200 flex items-center gap-2 flex-wrap">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span className="text-xs text-slate-500 font-medium">Executed by:</span>
                    {message.agentPath.map((agent, i) => (
                      <span
                        key={i}
                        className={`text-xs px-2.5 py-1 rounded-md border font-medium ${getAgentColor(agent)}`}
                      >
                        {agent.replace('_', ' ')}
                      </span>
                    ))}
                  </div>
                )}
                
                <div className="mt-3 text-xs text-slate-400 flex items-center gap-2">
                  <Clock className="w-3 h-3" />
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>

              {message.role === 'user' && (
                <div className="w-10 h-10 bg-slate-700 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg">
                  <User className="w-6 h-6 text-white" />
                </div>
              )}
            </div>
          ))}

          {/* Live Agent Communication Visualization */}
          {isLoading && (
            <div className="space-y-4">
              {/* Agent Communication Panel */}
              <AgentCommunication 
                agentPath={agentPath}
                currentAgent={currentAgent}
                isProcessing={isLoading}
              />

              {/* Live Updates from Agents */}
              {liveAgentUpdates.length > 0 && (
                <div className="bg-white border border-slate-200 rounded-2xl p-5 shadow-sm">
                  <div className="flex items-center gap-2 mb-4">
                    <Activity className="w-5 h-5 text-blue-600 animate-pulse" />
                    <h4 className="font-semibold text-slate-800">Live Agent Activity</h4>
                  </div>
                  <div className="space-y-3 max-h-48 overflow-y-auto custom-scrollbar">
                    {liveAgentUpdates.map((update, idx) => (
                      <div key={idx} className="flex items-start gap-3 text-sm animate-slide-up">
                        {update.type === 'agent' ? (
                          <>
                            <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center flex-shrink-0">
                              <Zap className="w-4 h-4 text-purple-600" />
                            </div>
                            <div>
                              <p className="font-medium text-slate-700">
                                {update.agent.replace('_', ' ')} activated
                              </p>
                              <p className="text-xs text-slate-400">
                                {new Date(update.timestamp).toLocaleTimeString()}
                              </p>
                            </div>
                          </>
                        ) : (
                          <>
                            <div className="w-8 h-8 bg-blue-100 rounded-lg flex items-center justify-center flex-shrink-0">
                              {getAgentIcon(update.agent)}
                            </div>
                            <div className="flex-1">
                              <p className="text-xs text-slate-500 mb-1">
                                {update.agent.replace('_', ' ')}
                              </p>
                              <p className="text-slate-700 line-clamp-2">
                                {update.content.substring(0, 100)}...
                              </p>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Typing Indicator */}
              <div className="flex gap-4 justify-start">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0 shadow-lg relative">
                  <Bot className="w-6 h-6 text-white" />
                  <div className="absolute inset-0 rounded-full border-2 border-white pulse-ring"></div>
                </div>
                <div className="bg-white border border-slate-200 rounded-2xl px-6 py-4 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="typing-indicator flex gap-1">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    <span className="text-slate-600 text-sm">
                      {currentAgent ? `${currentAgent.replace('_', ' ')} is thinking...` : 'Processing...'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white border-t border-slate-200 p-6 shadow-lg">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-3">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Ask about logs, documentation, or database queries..."
                disabled={isLoading}
                className="flex-1 px-5 py-4 border-2 border-slate-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50 disabled:text-slate-400 transition-all text-base"
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !inputValue.trim()}
                className="px-8 py-4 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center gap-2 font-medium"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span className="hidden sm:inline">Processing</span>
                  </>
                ) : (
                  <>
                    <Send className="w-5 h-5" />
                    <span className="hidden sm:inline">Send</span>
                  </>
                )}
              </button>
            </div>
            
            {threadId && (
              <div className="mt-3 text-xs text-slate-500 flex items-center gap-2">
                <MessageSquare className="w-3 h-3" />
                <span>Thread: <span className="font-mono bg-slate-100 px-2 py-1 rounded">{threadId}</span></span>
              </div>
            )}

            {/* Quick Actions */}
            <div className="mt-4 flex gap-2 flex-wrap">
              <button
                onClick={() => setInputValue("Compare orders GOOD001 and BAD001")}
                disabled={isLoading}
                className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-all border border-slate-200"
              >
                Compare Orders
              </button>
              <button
                onClick={() => setInputValue("What causes payment failures?")}
                disabled={isLoading}
                className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-all border border-slate-200"
              >
                Payment Failures
              </button>
              <button
                onClick={() => setInputValue("Show me all failed orders")}
                disabled={isLoading}
                className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-all border border-slate-200"
              >
                Failed Orders
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
