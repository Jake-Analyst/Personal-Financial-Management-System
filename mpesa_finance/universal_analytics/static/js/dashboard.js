(async function() {
  try {
    const profile = await fetch('/api/profile').then(r => r.json());
    const plans   = await fetch('/api/analysis-plan').then(r => r.json());
    const configs = await fetch('/api/chart-configs').then(r => r.json());
    const insights = await fetch('/api/insights').then(r => r.json());
    const growth   = await fetch('/api/kpi-growth').then(r => r.json());

    // ---- KPI CARDS ----
    const kpiRow = document.getElementById('kpiRow');
    const moneyColumns = profile.columns.filter(c => c.semantic_role === 'money');
    
    // If no money columns, show row count and date range as fallback
    if (moneyColumns.length === 0) {
      const summary = configs.find(c => c.type === 'kpi');
      if (summary) {
        for (let col in summary.data) {
          appendKpiCard(kpiRow, col, summary.data[col].sum || summary.data[col].avg, null);
        }
      } else {
        const card = createKpiCard('Rows', profile.row_count.toLocaleString(), '');
        kpiRow.appendChild(card);
      }
    } else {
      // Filter KPI config to get the enriched values
      const kpiConfig = configs.find(c => c.type === 'kpi');
      moneyColumns.forEach(col => {
        const kpi = kpiConfig?.data?.[col.name] || { sum: 0, avg: 0 };
        const growthVal = growth?.[col.name] ?? 0;
        appendKpiCard(kpiRow, col.name, kpi.sum || kpi.avg, growthVal);
      });
    }

    // Sum all income/expense automatically (if both money columns detected and have +/- context)
    if (moneyColumns.length >= 2) {
      const totalIncome = moneyColumns.find(c => c.name.toLowerCase().includes('received') || c.name.toLowerCase().includes('income'));
      const totalExpense = moneyColumns.find(c => c.name.toLowerCase().includes('sent') || c.name.toLowerCase().includes('expense'));
      if (totalIncome && totalExpense) {
        const incSum = configs.find(c => c.type === 'kpi')?.data?.[totalIncome.name]?.sum || 0;
        const expSum = configs.find(c => c.type === 'kpi')?.data?.[totalExpense.name]?.sum || 0;
        document.getElementById('kpiRow').innerHTML = ''; // remove original
        appendKpiCard(kpiRow, 'Total Income', incSum, growth?.[totalIncome.name] ?? 0);
        appendKpiCard(kpiRow, 'Total Expenses', expSum, growth?.[totalExpense.name] ?? 0);
        appendKpiCard(kpiRow, 'Net Balance', incSum - expSum, null);
        // Re-add other money columns
        moneyColumns.forEach(col => {
          if (col.name !== totalIncome.name && col.name !== totalExpense.name) {
            appendKpiCard(kpiRow, col.name, configs.find(c => c.type === 'kpi')?.data?.[col.name]?.sum || 0, growth?.[col.name] ?? 0);
          }
        });
      }
    }

    // ---- MODULES (Charts) ----
    const modulesContainer = document.getElementById('modulesContainer');
    const chartConfigs = configs.filter(c => c.type !== 'kpi' && c.type !== 'info');

    chartConfigs.forEach((cfg, idx) => {
      const wrapper = document.createElement('div');
      wrapper.className = 'module-card';
      wrapper.innerHTML = `<h3 class="text-lg font-semibold text-white mb-3 flex items-center gap-2">
        <i class="fas fa-chart-${cfg.type === 'line' ? 'line' : cfg.type === 'pie' ? 'pie' : 'bar'} text-indigo-400"></i>
        ${cfg.title || 'Chart'}
      </h3>`;

      if (cfg.type === 'heatmap' && cfg.data && cfg.xlabels) {
        wrapper.innerHTML += `<div id="heatmap-${idx}" class="overflow-x-auto w-full"></div>`;
        modulesContainer.appendChild(wrapper);
        setTimeout(() => renderHeatmap(cfg, `heatmap-${idx}`), 10);
      } else if (cfg.type !== 'heatmap') {
        wrapper.innerHTML += `<div class="chart-container"><canvas id="chart${idx}"></canvas></div>`;
        modulesContainer.appendChild(wrapper);
        setTimeout(() => drawChart(cfg, idx), 10);
      }
    });

    // ---- AI INSIGHTS ----
    const insightsList = document.getElementById('insightsList');
    insightsList.innerHTML = '';
    insights.forEach((text, i) => {
      const li = document.createElement('li');
      li.className = 'flex items-start gap-2 text-sm';
      const icon = text.includes('increased') || text.includes('outlier') ? 'fa-exclamation-triangle text-yellow-400' :
                   text.includes('decreased') ? 'fa-check-circle text-green-400' : 'fa-lightbulb text-purple-400';
      li.innerHTML = `<i class="fas ${icon} mt-0.5"></i><span>${text}</span>`;
      insightsList.appendChild(li);
    });

    // ---- BUDGET HEALTH ----
    const incomeCol = moneyColumns.find(c => c.name.toLowerCase().includes('received') || c.name.toLowerCase().includes('income'));
    const expenseCol = moneyColumns.find(c => c.name.toLowerCase().includes('sent') || c.name.toLowerCase().includes('expense'));
    if (incomeCol && expenseCol) {
      const inc = configs.find(c => c.type === 'kpi')?.data?.[incomeCol.name]?.sum || 0;
      const exp = configs.find(c => c.type === 'kpi')?.data?.[expenseCol.name]?.sum || 0;
      const budgetTarget = inc * 0.7;
      const usage = budgetTarget > 0 ? (exp / budgetTarget) * 100 : 0;
      document.getElementById('budgetPercent').textContent = Math.min(usage, 100).toFixed(0) + '%';
      document.getElementById('budgetBar').style.width = Math.min(usage, 100) + '%';
      document.getElementById('budgetLabel').textContent = usage <= 70 ? 'Finances healthy' : usage <= 90 ? 'Monitor spending' : 'Over budget!';
    }

    // ---- ALERTS ----
    if (moneyColumns.some(c => c.name.toLowerCase().includes('balance'))) {
      const balanceCol = moneyColumns.find(c => c.name.toLowerCase().includes('balance'));
      const bal = configs.find(c => c.type === 'kpi')?.data?.[balanceCol.name]?.sum || 0;
      if (bal < 5000) {
        document.getElementById('alertBadge').textContent = '1';
        insightsList.insertAdjacentHTML('afterbegin', `<li class="flex items-start gap-2 text-sm text-red-400">
          <i class="fas fa-exclamation-circle"></i> ⚠️ Low balance alert: KES ${bal.toLocaleString()}</li>`);
      }
    }

  } catch (err) {
    console.error('Dashboard error:', err);
    document.body.innerHTML = '<div class="text-white p-8">⚠️ Error loading dashboard. Please upload a valid dataset first.</div>';
  }
})();

// ---- Helper functions ----
function appendKpiCard(container, label, value, growth) {
  const card = document.createElement('div');
  card.className = 'kpi-card text-white';
  let growthHTML = '';
  if (typeof growth === 'number' && !isNaN(growth)) {
    const isUp = growth > 0;
    growthHTML = `<div class="flex items-center gap-1 mt-1 text-xs ${isUp ? 'text-green-400' : 'text-red-400'}">
      <i class="fas fa-${isUp ? 'arrow-up' : 'arrow-down'}"></i> ${Math.abs(growth).toFixed(1)}%
    </div>`;
  }
  card.innerHTML = `
    <p class="text-sm text-gray-400 uppercase tracking-wider">${label}</p>
    <p class="text-2xl font-bold">KES ${typeof value === 'number' ? value.toLocaleString() : value}</p>
    ${growthHTML}
  `;
  container.appendChild(card);
}

function drawChart(cfg, idx) {
  const ctx = document.getElementById(`chart${idx}`).getContext('2d');
  new Chart(ctx, {
    type: cfg.type === 'pie' ? 'doughnut' : cfg.type === 'line' ? 'line' : 'bar',
    data: {
      labels: cfg.labels,
      datasets: cfg.datasets.map(ds => ({
        label: ds.label || '',
        data: ds.data,
        backgroundColor: cfg.type === 'pie' ? ['#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444'] : '#6366f1',
        borderColor: '#4f46e5',
        borderWidth: 1,
        tension: cfg.type === 'line' ? 0.4 : undefined,
        fill: cfg.type === 'line' ? true : undefined
      }))
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#cbd5e1', usePointStyle: true, padding: 16, font: { size: 11 } } },
        tooltip: {
          backgroundColor: '#1e293b',
          titleColor: '#f1f5f9',
          bodyColor: '#cbd5e1',
          borderColor: '#475569',
          borderWidth: 1,
          cornerRadius: 8
        }
      },
      scales: cfg.type !== 'pie' ? {
        x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
        y: { ticks: { color: '#94a3b8', callback: v => 'KES ' + v.toLocaleString() }, grid: { color: 'rgba(148,163,184,0.1)' } }
      } : {}
    }
  });
}

function renderHeatmap(cfg, containerId) {
  const container = document.getElementById(containerId);
  const canvas = document.createElement('canvas');
  canvas.width = 800; canvas.height = 300;
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const matrix = cfg.data;
  const xlabels = cfg.xlabels;
  const ylabels = cfg.ylabels;
  const maxVal = Math.max(...matrix.flat(), 1);
  const cellW = 30, cellH = 25, margin = { top: 20, left: 40 };

  for (let r = 0; r < matrix.length; r++) {
    for (let c = 0; c < matrix[r].length; c++) {
      const intensity = matrix[r][c] / maxVal;
      ctx.fillStyle = `rgba(99,102,241,${intensity})`;
      ctx.fillRect(c * cellW + margin.left, r * cellH + margin.top, cellW - 1, cellH - 1);
    }
  }
  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px Inter';
  ylabels.forEach((l, i) => ctx.fillText(l, 0, i * cellH + margin.top + 15));
  xlabels.forEach((l, i) => {
    if (i % 3 === 0) ctx.fillText(l, i * cellW + margin.left, canvas.height - 5);
  });
}
