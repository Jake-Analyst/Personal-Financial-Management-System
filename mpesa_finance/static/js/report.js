document.addEventListener('DOMContentLoaded', async () => {
  const summary = await fetch('/api/summary').then(r => r.json());
  const cat = await fetch('/api/category_spending').then(r => r.json());
  const monthly = await fetch('/api/monthly_spending').then(r => r.json());
  const pred = await fetch('/api/predictions').then(r => r.json());

  let html = <div class=\"card shadow p-4 mb-4\"><h4>Financial Overview</h4>
      <p>Total Income: <strong>KES </strong></p>
      <p>Total Expenses: <strong>KES </strong></p>
      <p>Net Balance: <strong>KES </strong></p></div>;

  html += <div class=\"card shadow p-4 mb-4\"><h4>Spending Breakdown</h4><ul class=\"list-group list-group-flush\">;
  const totalExpense = cat.reduce((sum, c) => sum + c.amount, 0);
  cat.forEach(c => {
    const pct = ((c.amount / totalExpense)*100).toFixed(1);
    html += <li class=\"list-group-item d-flex justify-content-between\"><span></span><span>% (KES )</span></li>;
  });
  html += </ul></div>;

  if (cat.length) {
    const highest = cat.sort((a,b)=>b.amount-a.amount)[0];
    html += <div class=\"card shadow p-4 mb-4\"><h4>💡 Key Insight</h4><p>You spend the most on <strong></strong> – % of total expenses.</p></div>;
  }

  html += <div class=\"card shadow p-4 mb-4\"><h4>🔮 Next Month Forecast</h4>;
  if (pred.forecast) {
    html += <p>Forecasted expenses for : <strong>KES </strong></p>;
    html += <p class=\"text-muted\"></p>;
  }
  html += </div>;

  html += <div class=\"card shadow p-4\"><h4>📈 Recommendations</h4>;
  if (pred.recommendations && pred.recommendations.length) {
    html += <ul class=\"list-group\">;
    pred.recommendations.forEach(rec => {
      html += <li class=\"list-group-item list-group-item-\"></li>;
    });
    html += </ul>;
  } else {
    html += <p class=\"text-success\">Your spending is within healthy ranges. Keep it up!</p>;
  }
  html += </div>;

  document.getElementById('reportContent').innerHTML = html;
});
