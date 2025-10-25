import React, { useState, useEffect, useRef } from 'react';
import { Send, Bot, User, Clock, Database, BookOpen, FileText, Loader2, Trash2, MessageSquare } from 'lucide-react';

const API_BASE_URL = 'http://localhost:8000';

export default function LangGraphChatApp() {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [agentPath, setAgentPath] = useState([]);
  const [activeThreads, setActiveThreads] = useState([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    loadThreads();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

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
    } catch (error) {
      console.error('Error loading thread:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage = {
      role: 'user',
      content: inputValue,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setAgentPath([]);

    try {
      const response = await fetch(`${API_BASE_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: inputValue,
          thread_id: threadId
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

    } catch (error) {
      console.error('Error sending message:', error);
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
  };

  const deleteThread = async (tid) => {
    try {
      await fetch(`${API_BASE_URL}/threads/${tid}`, {
        method: 'DELETE'
      });
      
      if (tid === threadId) {
        setMessages([]);
        setThreadId(null);
        setAgentPath([]);
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
  };

  const getAgentIcon = (agent) => {
    switch (agent) {
      case 'log_team':
        return <FileText className="w-4 h-4" />;
      case 'knowledge_team':
        return <BookOpen className="w-4 h-4" />;
      case 'db_team':
        return <Database className="w-4 h-4" />;
      default:
        return <Bot className="w-4 h-4" />;
    }
  };

  const getAgentColor = (agent) => {
    switch (agent) {
      case 'log_team':
        return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'knowledge_team':
        return 'bg-blue-100 text-blue-700 border-blue-200';
      case 'db_team':
        return 'bg-green-100 text-green-700 border-green-200';
      case 'supervisor':
        return 'bg-purple-100 text-purple-700 border-purple-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Sidebar */}
      <div className="w-80 bg-white border-r border-slate-200 flex flex-col">
        <div className="p-6 border-b border-slate-200">
          <h1 className="text-2xl font-bold text-slate-800 mb-2">
            LangGraph Teams
          </h1>
          <p className="text-sm text-slate-600">
            Hierarchical Agent System
          </p>
        </div>

        <div className="p-4">
          <button
            onClick={newConversation}
            className="w-full bg-gradient-to-r from-blue-500 to-blue-600 text-white px-4 py-3 rounded-lg hover:from-blue-600 hover:to-blue-700 transition-all shadow-sm flex items-center justify-center gap-2 font-medium"
          >
            <MessageSquare className="w-5 h-5" />
            New Conversation
          </button>
        </div>

        {/* Threads List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Recent Conversations
          </h2>
          {activeThreads.map((thread) => (
            <div
              key={thread.thread_id}
              className={`p-3 rounded-lg border cursor-pointer transition-all group ${
                threadId === thread.thread_id
                  ? 'bg-blue-50 border-blue-200'
                  : 'bg-white border-slate-200 hover:border-slate-300'
              }`}
            >
              <div
                onClick={() => loadThread(thread.thread_id)}
                className="flex-1"
              >
                <p className="text-sm font-medium text-slate-800 truncate">
                  {thread.thread_id}
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  {thread.message_count} messages
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteThread(thread.thread_id);
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded transition-all"
              >
                <Trash2 className="w-4 h-4 text-red-600" />
              </button>
            </div>
          ))}
        </div>

        {/* Agent Path Display */}
        {agentPath.length > 0 && (
          <div className="p-4 bg-slate-50 border-t border-slate-200">
            <h3 className="text-xs font-semibold text-slate-600 mb-2">
              Agent Execution Path
            </h3>
            <div className="flex flex-wrap gap-2">
              {agentPath.map((agent, idx) => (
                <div
                  key={idx}
                  className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-medium border ${getAgentColor(agent)}`}
                >
                  {getAgentIcon(agent)}
                  <span>{agent}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <div className="bg-white border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
              <Bot className="w-6 h-6 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-slate-800">
                Hierarchical Agent Assistant
              </h2>
              <p className="text-sm text-slate-500">
                Log Analysis • Knowledge Base • Database Queries
              </p>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center">
              <div className="text-center max-w-2xl">
                <div className="w-20 h-20 bg-gradient-to-br from-blue-100 to-purple-100 rounded-2xl flex items-center justify-center mx-auto mb-6">
                  <Bot className="w-10 h-10 text-blue-600" />
                </div>
                <h3 className="text-2xl font-bold text-slate-800 mb-3">
                  Welcome to LangGraph Teams
                </h3>
                <p className="text-slate-600 mb-6">
                  Ask me to analyze logs, search documentation, or query the database.
                </p>
                <div className="grid grid-cols-3 gap-4 text-left">
                  <div className="p-4 bg-orange-50 border border-orange-200 rounded-lg">
                    <FileText className="w-6 h-6 text-orange-600 mb-2" />
                    <h4 className="font-semibold text-sm text-slate-800 mb-1">Log Analysis</h4>
                    <p className="text-xs text-slate-600">Compare orders and find failures</p>
                  </div>
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <BookOpen className="w-6 h-6 text-blue-600 mb-2" />
                    <h4 className="font-semibold text-sm text-slate-800 mb-1">Knowledge Base</h4>
                    <p className="text-xs text-slate-600">Search docs and guides</p>
                  </div>
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                    <Database className="w-6 h-6 text-green-600 mb-2" />
                    <h4 className="font-semibold text-sm text-slate-800 mb-1">Database</h4>
                    <p className="text-xs text-slate-600">Query data with natural language</p>
                  </div>
                </div>
                <div className="mt-8 text-sm text-slate-500">
                  Try: "Compare orders GOOD001 and BAD001" or "What causes payment failures?"
                </div>
              </div>
            </div>
          )}

          {messages.map((message, idx) => (
            <div
              key={idx}
              className={`flex gap-4 ${
                message.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {message.role === 'assistant' && (
                <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                  <Bot className="w-5 h-5 text-white" />
                </div>
              )}
              
              <div
                className={`max-w-3xl ${
                  message.role === 'user'
                    ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
                    : message.isError
                    ? 'bg-red-50 border border-red-200 text-red-800'
                    : 'bg-white border border-slate-200 text-slate-800'
                } rounded-2xl px-5 py-4 shadow-sm`}
              >
                <div className="prose prose-sm max-w-none">
                  {message.content.split('\n').map((line, i) => {
                    // Handle markdown-style formatting
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
                  })}
                </div>
                
                {message.agentPath && message.agentPath.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-200 flex items-center gap-2 flex-wrap">
                    <Clock className="w-3 h-3 text-slate-400" />
                    <span className="text-xs text-slate-500">Execution path:</span>
                    {message.agentPath.map((agent, i) => (
                      <span
                        key={i}
                        className={`text-xs px-2 py-0.5 rounded border ${getAgentColor(agent)}`}
                      >
                        {agent}
                      </span>
                    ))}
                  </div>
                )}
                
                <div className="mt-2 text-xs text-slate-400">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </div>
              </div>

              {message.role === 'user' && (
                <div className="w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center flex-shrink-0">
                  <User className="w-5 h-5 text-white" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-4 justify-start">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl px-5 py-4 shadow-sm">
                <div className="flex items-center gap-3">
                  <Loader2 className="w-5 h-5 text-blue-500 animate-spin" />
                  <span className="text-slate-600">Processing your request...</span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="bg-white border-t border-slate-200 p-6">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-3">
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="Ask about logs, documentation, or database queries..."
                disabled={isLoading}
                className="flex-1 px-4 py-3 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-slate-50 disabled:text-slate-400"
              />
              <button
                onClick={sendMessage}
                disabled={isLoading || !inputValue.trim()}
                className="px-6 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-lg hover:from-blue-600 hover:to-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-sm flex items-center gap-2 font-medium"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin" />
                ) : (
                  <Send className="w-5 h-5" />
                )}
                Send
              </button>
            </div>
            
            {threadId && (
              <div className="mt-3 text-xs text-slate-500">
                Thread ID: <span className="font-mono">{threadId}</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
