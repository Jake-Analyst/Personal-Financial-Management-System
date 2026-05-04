// Premium Interactive Dashboard with Heatmap + Precision Tooltips
let lineChart, donutChart, hourChart, senderChart, recipientChart, weekdayChart;
let sparkBalance, sparkIncome, sparkExpense, sparkSavings;
let allMonthlyData = [];
let currentCategoryFilter = '';

document.addEventListener('DOMContentLoaded', () => {
  setGreeting();
  loadCategoryChips();
  refreshAll();
  
  document.getElementById('startDate').addEventListener('change', refreshAll);
  document.getElementById('endDate').addEventListener('change', refreshAll);
  
  document.querySelectorAll('.quick-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      const days = parseInt(btn.dataset.range);
      const end = new Date();
      const start = new Date();
      start.setDate(end.getDate() - days);
      document.getElementById('startDate').value = formatDate(start);
      document.getElementById('endDate').value = formatDate(end);
      refreshAll();
    });
  });
  
  document.getElementById('clearCategoryFilter').addEventListener('click', () => {
    currentCategoryFilter = '';
    document.getElementById('clearCategoryFilter').style.display = 'none';
    document.querySelectorAll('.category-chip').forEach(c => {
      c.classList.remove('bg-accent', 'text-white');
      c.classList.add('bg-surface-lighter', 'text-slate-300');
    });
    const allChip = document.querySelector('.category-chip[data-category=""]');
    if (allChip) {
      allChip.classList.add('bg-accent', 'text-white');
      allChip.classList.remove('bg-surface-lighter', 'text-slate-300');
    }
    refreshAll();
  });
});

function formatDate(d) { return d.toISOString().split('T')[0]; }

function setGreeting() {
  const hour = new Date().getHours();
  const greetings = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  document.getElementById('greeting').textContent = greetings + ' 👋';
}

function getFilterParams() {
  let start = document.getElementById('startDate').value;
  let end = document.getElementById('endDate').value;
  if (start && end && start > end) {
    [start, end] = [end, start];
    document.getElementById('startDate').value = start;
    document.getElementById('endDate').value = end;
  }
  const params = {};
  if (start) params.start = start;
  if (end) params.end = end;
  if (currentCategoryFilter) params.category = currentCategoryFilter;
  return new URLSearchParams(params).toString();
}

async function loadCategoryChips() {
  try {
    const resp = await fetch('/api/category_spending');
    const data = await resp.json();
    const container = document.getElementById('categoryChips');
    container.innerHTML = '<button class="category-chip px-2.5 py-1 rounded-lg text-xs font-medium bg-accent text-white" data-category="">All</button>';
    data.forEach(item => {
      const chip = document.createElement('button');
      chip.className = 'category-chip px-2.5 py-1 rounded-lg text-xs font-medium bg-surface-lighter text-slate-300 hover:bg-accent/20 hover:text-accent-light transition-all';
      chip.dataset.category = item.category;
      chip.textContent = item.category;
      chip.addEventListener('click', () => {
        currentCategoryFilter = item.category;
        document.getElementById('clearCategoryFilter').style.display = 'inline-block';
        document.querySelectorAll('.category-chip').forEach(c => {
          c.classList.remove('bg-accent', 'text-white');
          c.classList.add('bg-surface-lighter', 'text-slate-300');
        });
        chip.classList.add('bg-accent', 'text-white');
        chip.classList.remove('bg-surface-lighter', 'text-slate-300');
        refreshAll();
      });
      container.appendChild(chip);
    });
    container.querySelector('[data-category=""]').addEventListener('click', function() {
      currentCategoryFilter = '';
      document.getElementById('clearCategoryFilter').style.display = 'none';
      document.querySelectorAll('.category-chip').forEach(c => {
        c.classList.remove('bg-accent', 'text-white');
        c.classList.add('bg-surface-lighter', 'text-slate-300');
      });
      this.classList.add('bg-accent', 'text-white');
      this.classList.remove('bg-surface-lighter', 'text-slate-300');
      refreshAll();
    });
  } catch (err) { console.error('Error loading categories:', err); }
}

async function refreshAll() {
  try {
    const params = getFilterParams();
    const [summary, catData, monthlyData, hourData, senderData, recipData, predData, heatmapData, weekdayData] = await Promise.all([
      fetch('/api/summary?' + params).then(r => r.json()),
      fetch('/api/category_spending?' + params).then(r => r.json()),
      fetch('/api/monthly_spending?' + params).then(r => r.json()),
      fetch('/api/spending_by_hour?' + params).then(r => r.json()),
      fetch('/api/top_income_senders?' + params + '&limit=8').then(r => r.json()),
      fetch('/api/top_expense_recipients?' + params + '&limit=8').then(r => r.json()),
      fetch('/api/predictions').then(r => r.json()),
      fetch('/api/heatmap?' + params).then(r => r.json()),
      fetch('/api/weekday_spending?' + params).then(r => r.json())
    ]);

    allMonthlyData = monthlyData;
    updateKPIs(summary, monthlyData);
    updateAIInsights(summary, catData, monthlyData, heatmapData);
    updateBudgetHealth(summary);
    updatePredictions(predData);
    drawLineChart(monthlyData);
    drawDonutChart(catData);
    drawHourChart(hourData);
    drawSenderChart(senderData);
    drawRecipientChart(recipData);
    drawHeatmap(heatmapData);
    drawWeekdayChart(weekdayData);
    
    document.getElementById('aiInsight').textContent = generateAISummary(summary, catData);
  } catch (err) { console.error('Error refreshing dashboard:', err); }
}

// ---- KPI Updates ----
function updateKPIs(summary, monthlyData) {
  animateValue('totalBalance', summary.balance);
  animateValue('totalIncome', summary.income);
  animateValue('totalExpenses', summary.expenses);
  const savingsRate = summary.income > 0 ? ((summary.income - summary.expenses) / summary.income * 100) : 0;
  document.getElementById('savingsRate').textContent = savingsRate.toFixed(1) + '%';
  
  if (monthlyData.length >= 2) {
    const last = monthlyData[monthlyData.length - 1].expenses;
    const prev = monthlyData[monthlyData.length - 2].expenses;
    const change = prev > 0 ? ((last - prev) / prev * 100) : 0;
    const trendEl = document.getElementById('expenseTrend');
    trendEl.innerHTML = change > 0 ? '<i class="fas fa-arrow-up text-[10px]"></i><span>' + Math.abs(change).toFixed(1) + '%</span>' : '<i class="fas fa-arrow-down text-[10px]"></i><span>' + Math.abs(change).toFixed(1) + '%</span>';
    trendEl.className = change > 0 ? 'text-xs font-medium text-red-400 bg-red-400/10 px-2 py-0.5 rounded-full flex items-center gap-1' : 'text-xs font-medium text-green-400 bg-green-400/10 px-2 py-0.5 rounded-full flex items-center gap-1';
  }
  drawSparkline('sparkBalance', monthlyData, '#6366f1');
  drawSparkline('sparkIncome', monthlyData, '#10b981');
  drawSparkline('sparkExpense', monthlyData, '#ef4444');
  drawSparkline('sparkSavings', monthlyData, '#a855f7');
}

function animateValue(id, value) {
  const el = document.getElementById(id);
  const start = parseInt(el.textContent.replace(/[^0-9.-]/g, '')) || 0;
  const end = value;
  const duration = 600;
  const startTime = performance.now();
  function update(now) {
    const elapsed = now - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = 'KES ' + Math.round(start + (end - start) * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}

function drawSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.parentElement.clientWidth;
  canvas.height = 24;
  const values = data.map(d => d.expenses);
  if (values.length < 2) return;
  const min = Math.min(...values), max = Math.max(...values), range = max - min || 1;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.beginPath();
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  values.forEach((v, i) => {
    const x = (i / (values.length - 1)) * canvas.width;
    const y = canvas.height - ((v - min) / range) * (canvas.height - 6) - 3;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function generateAISummary(summary, catData) {
  if (!catData.length) return 'Upload transactions to get AI-powered insights.';
  const top = catData.sort((a,b) => b.amount - a.amount)[0];
  return 'Your top spending category is ' + top.category + ' at ' + ((top.amount/summary.expenses)*100).toFixed(0) + '% of total.';
}

// ---- AI Insights ----
function updateAIInsights(summary, catData, monthlyData, heatmapData) {
  const insights = [];
  
  if (monthlyData.length >= 2) {
    const last = monthlyData[monthlyData.length - 1].expenses;
    const prev = monthlyData[monthlyData.length - 2].expenses;
    const pctChange = ((last - prev) / prev * 100);
    if (pctChange > 10) insights.push({ icon: 'fa-exclamation-triangle', color: 'text-yellow-400', text: 'Spending increased ' + pctChange.toFixed(0) + '% vs last period' });
    else if (pctChange < -10) insights.push({ icon: 'fa-check-circle', color: 'text-green-400', text: 'Spending decreased ' + Math.abs(pctChange).toFixed(0) + '% - great job!' });
  }
  
  // Heatmap insights
  if (heatmapData && heatmapData.length > 0) {
    // Find peak day-hour combo
    const peak = heatmapData.reduce((a, b) => a.amount > b.amount ? a : b);
    const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
    const peakDay = dayNames[peak.day];
    const peakHour = peak.hour;
    const ampm = peakHour >= 12 ? 'PM' : 'AM';
    const displayHour = peakHour > 12 ? peakHour - 12 : (peakHour === 0 ? 12 : peakHour);
    insights.push({ icon: 'fa-fire', color: 'text-orange-400', text: 'Peak spending: ' + peakDay + 's at ' + displayHour + ampm + ' (KES ' + peak.amount.toLocaleString() + ')' });
    
    // Evening spending pattern
    const eveningTotal = heatmapData.filter(h => h.hour >= 18 && h.hour <= 21).reduce((s, h) => s + h.amount, 0);
    const totalHeatmap = heatmapData.reduce((s, h) => s + h.amount, 0);
    if (totalHeatmap > 0 && eveningTotal / totalHeatmap > 0.3) {
      insights.push({ icon: 'fa-moon', color: 'text-blue-400', text: ((eveningTotal/totalHeatmap)*100).toFixed(0) + '% of spending occurs between 6PM-9PM' });
    }
    
    // Weekend vs weekday
    const weekendTotal = heatmapData.filter(h => h.day >= 5).reduce((s, h) => s + h.amount, 0);
    if (totalHeatmap > 0 && weekendTotal / totalHeatmap > 0.25) {
      insights.push({ icon: 'fa-umbrella-beach', color: 'text-purple-400', text: ((weekendTotal/totalHeatmap)*100).toFixed(0) + '% of spending happens on weekends' });
    }
  }
  
  if (summary.income > 0 && summary.expenses > summary.income * 0.8) {
    insights.push({ icon: 'fa-exclamation-circle', color: 'text-red-400', text: 'Expenses are over 80% of income - consider cutting back' });
  }
  if (summary.balance > summary.income * 0.3) {
    insights.push({ icon: 'fa-lightbulb', color: 'text-accent-light', text: 'Strong balance! Consider investing surplus funds' });
  }
  if (insights.length === 0) {
    insights.push({ icon: 'fa-smile', color: 'text-green-400', text: 'Your finances look healthy!' });
  }
  
  document.getElementById('aiInsightsList').innerHTML = insights.map(i => 
    '<div class="flex items-start gap-2"><i class="fas ' + i.icon + ' ' + i.color + ' mt-0.5"></i><p>' + i.text + '</p></div>'
  ).join('');
}

function updateBudgetHealth(summary) {
  const budget = summary.income * 0.7;
  const usage = budget > 0 ? (summary.expenses / budget * 100) : 0;
  const clamped = Math.min(usage, 100);
  document.getElementById('budgetPercent').textContent = clamped.toFixed(0) + '%';
  document.getElementById('budgetBar').style.width = clamped + '%';
  if (clamped < 50) {
    document.getElementById('budgetBar').className = 'h-full bg-gradient-to-r from-green-500 to-green-400 rounded-full transition-all duration-700';
    document.getElementById('budgetLabel').textContent = 'Well under budget!';
  } else if (clamped < 80) {
    document.getElementById('budgetBar').className = 'h-full bg-gradient-to-r from-yellow-500 to-yellow-400 rounded-full transition-all duration-700';
    document.getElementById('budgetLabel').textContent = 'Approaching budget limit';
  } else {
    document.getElementById('budgetBar').className = 'h-full bg-gradient-to-r from-red-600 to-red-500 rounded-full transition-all duration-700';
    document.getElementById('budgetLabel').textContent = 'Over budget! Review spending';
  }
  if (budget === 0) document.getElementById('budgetLabel').textContent = 'No income data yet';
}

function updatePredictions(predData) {
  if (predData.forecast && predData.forecast.forecast) {
    document.getElementById('forecastAmount').textContent = 'KES ' + predData.forecast.forecast.toLocaleString();
    document.getElementById('forecastSave').textContent = 'KES ' + Math.round(predData.forecast.forecast * 0.2).toLocaleString();
  }
}

// ---- CHARTS ----

function drawLineChart(data) {
  if (lineChart) lineChart.destroy();
  const ctx = document.getElementById('lineChart').getContext('2d');
  if (data.length === 0) return;
  const gradient = ctx.createLinearGradient(0, 0, 0, 400);
  gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
  gradient.addColorStop(1, 'rgba(99, 102, 241, 0)');
  
  lineChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => d.date),
      datasets: [{
        label: 'Spending',
        data: data.map(d => d.expenses),
        borderColor: '#818cf8',
        backgroundColor: gradient,
        fill: true,
        tension: 0.4,
        pointRadius: 3,
        pointBackgroundColor: '#818cf8',
        borderWidth: 2.5
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          borderColor: '#475569',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            label: ctx => 'KES ' + ctx.parsed.y.toLocaleString()
          }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { color: 'rgba(148,163,184,0.1)' } },
        y: { ticks: { color: '#94a3b8', callback: v => 'KES ' + v.toLocaleString() }, grid: { color: 'rgba(148,163,184,0.1)' }, beginAtZero: true }
      },
      interaction: { intersect: false, mode: 'index' }
    }
  });
}

function drawDonutChart(data) {
  if (donutChart) donutChart.destroy();
  const ctx = document.getElementById('donutChart').getContext('2d');
  if (data.length === 0) return;
  
  donutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: data.map(d => d.category),
      datasets: [{
        data: data.map(d => d.amount),
        backgroundColor: ['#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444','#06b6d4'],
        borderWidth: 0,
        hoverBorderWidth: 3,
        hoverBorderColor: '#1e293b'
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      onClick: (event, elements) => {
        if (elements.length > 0) {
          const idx = elements[0].index;
          const category = data[idx].category;
          currentCategoryFilter = category;
          document.getElementById('clearCategoryFilter').style.display = 'inline-block';
          document.querySelectorAll('.category-chip').forEach(c => {
            c.classList.remove('bg-accent', 'text-white');
            c.classList.add('bg-surface-lighter', 'text-slate-300');
            if (c.dataset.category === category) {
              c.classList.add('bg-accent', 'text-white');
              c.classList.remove('bg-surface-lighter', 'text-slate-300');
            }
          });
          refreshAll();
        }
      },
      plugins: {
        legend: { position: 'bottom', labels: { color: '#94a3b8', padding: 12, usePointStyle: true, pointStyleWidth: 6, font: { size: 9 } } },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          borderColor: '#475569',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            label: ctx => {
              const item = data[ctx.dataIndex];
              const total = ctx.dataset.data.reduce((a,b) => a+b, 0);
              const pct = ((item.amount / total)*100).toFixed(1);
              return [
                'KES ' + item.amount.toLocaleString(),
                pct + '% of total',
                item.count + ' transactions'
              ];
            }
          }
        }
      }
    }
  });
}

function drawHourChart(data) {
  if (hourChart) hourChart.destroy();
  const ctx = document.getElementById('hourChart').getContext('2d');
  if (data.length === 0) return;
  
  hourChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.hour + ':00'),
      datasets: [{
        data: data.map(d => d.amount),
        backgroundColor: '#8b5cf6',
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          borderColor: '#475569',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            title: ctx => ctx[0].label,
            label: ctx => {
              const item = data[ctx.dataIndex];
              return ['KES ' + item.amount.toLocaleString(), item.count + ' transactions'];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' }, beginAtZero: true }
      }
    }
  });
}

function drawWeekdayChart(data) {
  if (weekdayChart) weekdayChart.destroy();
  const ctx = document.getElementById('weekdayChart').getContext('2d');
  if (data.length === 0) return;
  
  const colors = data.map(d => d.day === 'Saturday' || d.day === 'Sunday' ? '#f59e0b' : '#6366f1');
  
  weekdayChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.day.substring(0, 3)),
      datasets: [{
        data: data.map(d => d.amount),
        backgroundColor: colors,
        borderRadius: 4,
        borderSkipped: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          borderColor: '#475569',
          borderWidth: 1,
          cornerRadius: 8,
          callbacks: {
            label: ctx => {
              const item = data[ctx.dataIndex];
              return ['KES ' + item.amount.toLocaleString(), item.count + ' transactions'];
            }
          }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8', font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' }, beginAtZero: true }
      }
    }
  });
}

function drawSenderChart(data) {
  if (senderChart) senderChart.destroy();
  const ctx = document.getElementById('senderChart').getContext('2d');
  if (data.length === 0) return;
  senderChart = new Chart(ctx, {
    type: 'bar', indexAxis: 'y',
    data: {
      labels: data.map(d => d.name.length > 18 ? d.name.substring(0,16)+'..' : d.name),
      datasets: [{ data: data.map(d => d.amount), backgroundColor: '#10b981', borderRadius: 4, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b', borderColor: '#475569', borderWidth: 1, cornerRadius: 8,
          callbacks: { label: ctx => 'KES ' + ctx.parsed.x.toLocaleString() }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' }, beginAtZero: true },
        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } }
      }
    }
  });
}

function drawRecipientChart(data) {
  if (recipientChart) recipientChart.destroy();
  const ctx = document.getElementById('recipientChart').getContext('2d');
  if (data.length === 0) return;
  recipientChart = new Chart(ctx, {
    type: 'bar', indexAxis: 'y',
    data: {
      labels: data.map(d => d.name.length > 18 ? d.name.substring(0,16)+'..' : d.name),
      datasets: [{ data: data.map(d => d.amount), backgroundColor: '#ef4444', borderRadius: 4, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#1e293b', borderColor: '#475569', borderWidth: 1, cornerRadius: 8,
          callbacks: { label: ctx => 'KES ' + ctx.parsed.x.toLocaleString() }
        }
      },
      scales: {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' }, beginAtZero: true },
        y: { ticks: { color: '#94a3b8', font: { size: 9 } }, grid: { display: false } }
      }
    }
  });
}

// ---- CUSTOM HEATMAP ----
function drawHeatmap(data) {
  const container = document.getElementById('heatmapContainer');
  const canvas = document.getElementById('heatmapCanvas');
  const tooltip = document.getElementById('heatmapTooltip');
  if (!canvas || !container || data.length === 0) return;
  
  const rect = container.getBoundingClientRect();
  canvas.width = rect.width;
  canvas.height = rect.height;
  const ctx = canvas.getContext('2d');
  
  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  const hours = 24;
  const margin = { top: 15, right: 15, bottom: 25, left: 35 };
  const cellW = (canvas.width - margin.left - margin.right) / hours;
  const cellH = (canvas.height - margin.top - margin.bottom) / 7;
  
  // Build data grid
  const grid = {};
  data.forEach(d => { grid[d.day + '-' + d.hour] = d; });
  
  const maxAmount = Math.max(...data.map(d => d.amount), 1);
  
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  
  // Draw cells
  for (let day = 0; day < 7; day++) {
    for (let hour = 0; hour < 24; hour++) {
      const key = day + '-' + hour;
      const cell = grid[key];
      const x = margin.left + hour * cellW;
      const y = margin.top + day * cellH;
      
      if (cell) {
        const intensity = Math.min(cell.amount / maxAmount, 1);
        const r = Math.round(30 + intensity * 200);
        const g = Math.round(30 + (1 - intensity) * 100);
        const b = Math.round(80 + intensity * 150);
        ctx.fillStyle = 'rgb(' + r + ',' + g + ',' + b + ')';
      } else {
        ctx.fillStyle = '#1a2332';
      }
      
      ctx.fillRect(x + 1, y + 1, cellW - 2, cellH - 2);
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 0.5;
      ctx.strokeRect(x + 1, y + 1, cellW - 2, cellH - 2);
    }
  }
  
  // Labels
  ctx.fillStyle = '#94a3b8';
  ctx.font = '9px Inter, sans-serif';
  for (let i = 0; i < 7; i++) {
    ctx.fillText(days[i], 2, margin.top + i * cellH + cellH/2 + 3);
  }
  for (let h = 0; h < 24; h += 3) {
    ctx.fillText(h + '', margin.left + h * cellW + cellW/2 - 5, canvas.height - 4);
  }
  
  // Hover handler
  canvas.onmousemove = function(e) {
    const mx = e.offsetX;
    const my = e.offsetY;
    const hour = Math.floor((mx - margin.left) / cellW);
    const day = Math.floor((my - margin.top) / cellH);
    
    if (hour >= 0 && hour < 24 && day >= 0 && day < 7) {
      const key = day + '-' + hour;
      const cell = grid[key];
      if (cell) {
        const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        const ampm = hour >= 12 ? 'PM' : 'AM';
        const displayHour = hour > 12 ? hour - 12 : (hour === 0 ? 12 : hour);
        tooltip.innerHTML = '<div class="font-semibold mb-1">' + dayNames[day] + ' at ' + displayHour + ampm + '</div>' +
          '<div>KES ' + cell.amount.toLocaleString() + '</div>' +
          '<div class="text-slate-400">' + cell.count + ' transactions</div>';
        tooltip.style.display = 'block';
        tooltip.style.top = (my - 70) + 'px';
        tooltip.style.left = (mx + 10) + 'px';
        canvas.style.cursor = 'pointer';
      } else {
        tooltip.style.display = 'none';
        canvas.style.cursor = 'default';
      }
    } else {
      tooltip.style.display = 'none';
      canvas.style.cursor = 'default';
    }
  };
  
  canvas.onmouseleave = function() {
    tooltip.style.display = 'none';
  };
}
