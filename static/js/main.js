// Sterling Budget Tracker Client Application
document.addEventListener('DOMContentLoaded', () => {
    // State management
    let state = {
        transactions: [],
        summary: {},
        deleteTargetId: null,
        editTargetId: null,
        chartInstance: null
    };

    // Category lists
    const categories = {
        income: ['Salary', 'Freelance', 'Investments', 'Gifts', 'Other'],
        expense: ['Housing', 'Utilities', 'Groceries', 'Dining Out', 'Entertainment', 'Transport', 'Telecom', 'Health & Fitness', 'Shopping', 'Miscellaneous']
    };

    // DOM Elements
    const elements = {
        exportCsvBtn: document.getElementById('export-csv-btn'),
        openAddModalBtn: document.getElementById('open-add-modal-btn'),
        closeAddModalBtn: document.getElementById('close-add-modal-btn'),
        addModal: document.getElementById('add-modal'),
        addForm: document.getElementById('add-transaction-form'),
        modalTitle: document.getElementById('modal-title-add'),
        modalSubmitBtn: document.getElementById('save-transaction-btn'),
        
        closeDeleteModalBtn: document.getElementById('close-delete-modal-btn'),
        confirmDeleteBtn: document.getElementById('confirm-delete-btn'),
        deleteModal: document.getElementById('delete-modal'),
        
        txTypeExpense: document.getElementById('tx-type-expense'),
        txTypeIncome: document.getElementById('tx-type-income'),
        txCategory: document.getElementById('tx-category'),
        txDate: document.getElementById('tx-date'),
        txAmount: document.getElementById('tx-amount'),
        txDesc: document.getElementById('tx-desc'),
        
        filterType: document.getElementById('filter-type'),
        filterCategory: document.getElementById('filter-category'),
        searchTx: document.getElementById('search-tx'),
        
        transactionsBody: document.getElementById('transactions-body'),
        listLoader: document.getElementById('list-loader'),
        emptyState: document.getElementById('empty-state'),
        
        valBalance: document.getElementById('val-balance'),
        valIncome: document.getElementById('val-income'),
        valExpense: document.getElementById('val-expense'),
        
        toastContainer: document.getElementById('toast-container'),
        chartCanvas: document.getElementById('expenseChart'),
        chartPlaceholder: document.getElementById('chart-placeholder')
    };

    // --- Toast Notifications ---
    function showToast(message, type = 'success') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
        toast.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;
        
        elements.toastContainer.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Remove toast
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 350);
        }, 3000);
    }

    // --- Currency Formatter (GBP) ---
    const currencyFormatter = new Intl.NumberFormat('en-GB', {
        style: 'currency',
        currency: 'GBP'
    });

    function formatCurrency(amount) {
        return currencyFormatter.format(amount);
    }

    // --- Category Dropdown Populator ---
    function populateFormCategories(type, selectedCategory = '') {
        elements.txCategory.innerHTML = '';
        const list = [...(categories[type] || [])];
        if (selectedCategory && !list.includes(selectedCategory)) {
            list.push(selectedCategory);
        }
        list.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            elements.txCategory.appendChild(opt);
        });
        if (selectedCategory) {
            elements.txCategory.value = selectedCategory;
        }
    }

    function populateFilterCategories() {
        const selectedValue = elements.filterCategory.value;
        elements.filterCategory.innerHTML = '<option value="">All Categories</option>';
        
        // Add both income and expense categories to filter dropdown
        const allCats = [...categories.income, ...categories.expense];
        allCats.sort().forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat.toLowerCase();
            opt.textContent = cat;
            elements.filterCategory.appendChild(opt);
        });
        
        // Keep selected filter if still valid
        elements.filterCategory.value = selectedValue;
    }

    // Toggle Category in Modal based on radio selection
    elements.txTypeExpense.addEventListener('change', () => populateFormCategories('expense'));
    elements.txTypeIncome.addEventListener('change', () => populateFormCategories('income'));

    // --- Modal Handlers ---
    function openModal(modal) {
        modal.classList.add('open');
    }

    function closeModal(modal) {
        modal.classList.remove('open');
    }

    function resetTransactionForm() {
        elements.addForm.reset();
        elements.txTypeExpense.checked = true;
        populateFormCategories('expense');
        elements.txDate.value = new Date().toISOString().split('T')[0];
        elements.modalTitle.innerHTML = '<i class="fa-solid fa-circle-plus" style="color: var(--primary);"></i> Add Transaction';
        elements.modalSubmitBtn.innerHTML = 'Save Transaction';
        state.editTargetId = null;
    }

    function openAddModal() {
        resetTransactionForm();
        openModal(elements.addModal);
    }

    function openEditModal(tx) {
        resetTransactionForm();
        state.editTargetId = tx.id;
        elements.txDesc.value = tx.description;
        elements.txAmount.value = tx.amount;
        elements.txDate.value = tx.date;
        elements.txCategory.value = tx.category;

        if (tx.type === 'income') {
            elements.txTypeIncome.checked = true;
            populateFormCategories('income', tx.category);
        } else {
            elements.txTypeExpense.checked = true;
            populateFormCategories('expense', tx.category);
        }

        elements.modalTitle.innerHTML = '<i class="fa-solid fa-pen-to-square" style="color: var(--primary);"></i> Edit Transaction';
        elements.modalSubmitBtn.innerHTML = 'Update Transaction';
        openModal(elements.addModal);
    }

    elements.exportCsvBtn.addEventListener('click', () => {
        window.location.href = '/api/transactions/download';
    });

    elements.openAddModalBtn.addEventListener('click', openAddModal);

    elements.closeAddModalBtn.addEventListener('click', () => {
        closeModal(elements.addModal);
        resetTransactionForm();
    });
    elements.closeDeleteModalBtn.addEventListener('click', () => closeModal(elements.deleteModal));

    // Close modals on backdrop click
    window.addEventListener('click', (e) => {
        if (e.target === elements.addModal) {
            closeModal(elements.addModal);
            resetTransactionForm();
        }
        if (e.target === elements.deleteModal) closeModal(elements.deleteModal);
    });

    // --- Chart Handler (Chart.js) ---
    function updateChart(categoryData) {
        const labels = Object.keys(categoryData);
        const data = Object.values(categoryData);

        if (labels.length === 0) {
            elements.chartCanvas.style.display = 'none';
            elements.chartPlaceholder.style.display = 'flex';
            return;
        }

        elements.chartCanvas.style.display = 'block';
        elements.chartPlaceholder.style.display = 'none';

        // Custom vibrant neon palette for Chart
        const colors = [
            '#6366f1', // Indigo
            '#a855f7', // Purple
            '#ec4899', // Pink
            '#f43f5e', // Rose
            '#3b82f6', // Blue
            '#06b6d4', // Cyan
            '#14b8a6', // Teal
            '#10b981', // Emerald
            '#f59e0b', // Amber
            '#ef4444'  // Red
        ];

        if (state.chartInstance) {
            state.chartInstance.destroy();
        }

        const ctx = elements.chartCanvas.getContext('2d');
        state.chartInstance = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors.slice(0, labels.length),
                    borderWidth: 1,
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    hoverOffset: 12
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#9ca3af',
                            font: {
                                family: 'Inter',
                                size: 12
                            },
                            padding: 15
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(17, 25, 40, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(255, 255, 255, 0.1)',
                        borderWidth: 1,
                        padding: 12,
                        boxPadding: 8,
                        callbacks: {
                            label: function(context) {
                                return ` ${context.label}: ${formatCurrency(context.parsed)}`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }

    // --- Render KPI cards ---
    function renderKPIs(summary) {
        // Balance formatting with visual positive/negative sign colors
        const balance = summary.balance || 0;
        elements.valBalance.textContent = formatCurrency(balance);
        if (balance < 0) {
            elements.valBalance.style.color = 'var(--expense)';
        } else {
            elements.valBalance.style.color = '#ffffff';
        }
        
        elements.valIncome.textContent = formatCurrency(summary.total_income || 0);
        elements.valExpense.textContent = formatCurrency(summary.total_expense || 0);
    }

    // --- Load Data from API ---
    async function fetchTransactions() {
        elements.listLoader.style.display = 'flex';
        elements.emptyState.style.display = 'none';
        
        const searchQuery = elements.searchTx.value;
        const typeFilter = elements.filterType.value;
        const categoryFilter = elements.filterCategory.value;
        
        const params = new URLSearchParams();
        if (searchQuery) params.append('search', searchQuery);
        if (typeFilter) params.append('type', typeFilter);
        if (categoryFilter) params.append('category', categoryFilter);

        try {
            const response = await fetch(`/api/transactions?${params.toString()}`);
            const data = await response.json();
            
            if (data.success) {
                state.transactions = data.transactions;
                state.summary = data.summary;
                
                renderKPIs(data.summary);
                renderTable(data.transactions);
                updateChart(data.summary.categories);
            } else {
                showToast(data.error || 'Failed to load transactions', 'error');
            }
        } catch (error) {
            showToast('Network error loading data', 'error');
            console.error(error);
        } finally {
            elements.listLoader.style.display = 'none';
        }
    }

    // --- Render Transactions Table ---
    function renderTable(txList) {
        elements.transactionsBody.innerHTML = '';
        
        if (txList.length === 0) {
            elements.emptyState.style.display = 'flex';
            return;
        }
        
        elements.emptyState.style.display = 'none';
        
        txList.forEach(tx => {
            const tr = document.createElement('tr');
            tr.className = 'tx-row';
            tr.dataset.id = tx.id;
            
            // Format dates neatly
            const dateObj = new Date(tx.date);
            const formattedDate = dateObj.toLocaleDateString('en-GB', {
                day: 'numeric',
                month: 'short',
                year: 'numeric'
            });
            
            const badgeClass = tx.type === 'income' ? 'badge-income' : 'badge-expense';
            const amountClass = tx.type === 'income' ? 'amount-income' : 'amount-expense';
            const amountPrefix = tx.type === 'income' ? '+' : '-';
            
            tr.innerHTML = `
                <td>${formattedDate}</td>
                <td>
                    <div style="font-weight: 500;">${escapeHTML(tx.description)}</div>
                </td>
                <td>
                    <span class="badge badge-category">${escapeHTML(tx.category)}</span>
                </td>
                <td>
                    <span class="${amountClass}">
                        ${amountPrefix}${formatCurrency(tx.amount)}
                    </span>
                </td>
                <td style="text-align: center;">
                    <button class="btn-icon-edit" data-id="${tx.id}" aria-label="Edit transaction">
                        <i class="fa-regular fa-pen-to-square"></i>
                    </button>
                    <button class="btn-icon-delete" data-id="${tx.id}" aria-label="Delete transaction">
                        <i class="fa-regular fa-trash-can"></i>
                    </button>
                </td>
            `;
            
            tr.querySelector('.btn-icon-edit').addEventListener('click', (e) => {
                const txId = e.currentTarget.dataset.id;
                const tx = state.transactions.find(item => item.id === txId);
                if (tx) {
                    openEditModal(tx);
                }
            });

            tr.querySelector('.btn-icon-delete').addEventListener('click', (e) => {
                const txId = e.currentTarget.dataset.id;
                state.deleteTargetId = txId;
                openModal(elements.deleteModal);
            });
            
            elements.transactionsBody.appendChild(tr);
        });
    }

    // Helper to prevent HTML Injection
    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }

    // --- Add Transaction Form Submittal ---
    elements.addForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const description = elements.txDesc.value.trim();
        const amount = parseFloat(elements.txAmount.value);
        const date = elements.txDate.value;
        const category = elements.txCategory.value;
        const type = document.querySelector('input[name="type"]:checked').value;
        
        if (!description) {
            showToast('Please enter a description', 'error');
            return;
        }
        if (isNaN(amount) || amount <= 0) {
            showToast('Amount must be a positive number', 'error');
            return;
        }
        if (!date) {
            showToast('Please select a date', 'error');
            return;
        }
        if (!category) {
            showToast('Please select a category', 'error');
            return;
        }

        const payload = { description, amount, date, category, type };

        try {
            const url = state.editTargetId ? `/api/transactions/${state.editTargetId}` : '/api/transactions';
            const method = state.editTargetId ? 'PUT' : 'POST';
            const response = await fetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            
            if (data.success) {
                showToast(state.editTargetId ? 'Transaction updated successfully!' : 'Transaction added successfully!');
                closeModal(elements.addModal);
                resetTransactionForm();
                fetchTransactions();
            } else {
                showToast(data.error || 'Failed to save transaction', 'error');
            }
        } catch (error) {
            showToast('Network error saving transaction', 'error');
            console.error(error);
        }
    });

    // --- Confirm Deletion Handler ---
    elements.confirmDeleteBtn.addEventListener('click', async () => {
        const txId = state.deleteTargetId;
        if (!txId) return;

        try {
            const response = await fetch(`/api/transactions/${txId}`, {
                method: 'DELETE'
            });
            const data = await response.json();

            if (data.success) {
                closeModal(elements.deleteModal);
                
                // Add fade-out animation to table row before refetching
                const row = elements.transactionsBody.querySelector(`tr[data-id="${txId}"]`);
                if (row) {
                    row.classList.add('fade-out');
                    row.addEventListener('animationend', () => {
                        fetchTransactions();
                    });
                } else {
                    fetchTransactions();
                }
                
                showToast('Transaction deleted successfully');
            } else {
                showToast(data.error || 'Failed to delete transaction', 'error');
            }
        } catch (error) {
            showToast('Network error deleting transaction', 'error');
            console.error(error);
        } finally {
            state.deleteTargetId = null;
        }
    });

    // --- Search and Filters Listeners ---
    let searchTimeout = null;
    elements.searchTx.addEventListener('input', () => {
        // Debounce search requests
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            fetchTransactions();
        }, 300);
    });

    elements.filterType.addEventListener('change', () => {
        fetchTransactions();
    });

    elements.filterCategory.addEventListener('change', () => {
        fetchTransactions();
    });

    // --- Initial Bootstrapping ---
    populateFilterCategories();
    populateFormCategories('expense');
    fetchTransactions();
});
