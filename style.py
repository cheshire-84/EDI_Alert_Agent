# style.py - Modern Glassmorphism Dark Theme & QSS

DARK_GLASS_STYLE = """
/* =========================================================================
   Global Application & Window Base
   ========================================================================= */
QApplication {
    background-color: #0b0f19;
    color: #f8fafc;
    font-family: "Inter", "Noto Sans", "Cantarell", "DejaVu Sans", sans-serif;
    font-size: 13px;
}

QDialog, QWidget {
    background-color: #0b0f19;
    color: #f8fafc;
}

/* =========================================================================
   Dashboard Metric Cards (Top Summary Row)
   ========================================================================= */
QFrame#MetricCard {
    background-color: #131c2e;
    border: 1px solid #1e293b;
    border-left: 3px solid #334155;
    border-radius: 10px;
}

QFrame#MetricCard[accent="blue"] {
    border-left: 3px solid #3b82f6;
}

QFrame#MetricCard[accent="green"] {
    border-left: 3px solid #2ecc71;
}

QFrame#MetricCard[accent="red"] {
    border-left: 3px solid #e74c3c;
}

QFrame#MetricCard[accent="purple"] {
    border-left: 3px solid #8b5cf6;
}

QLabel#MetricTitle {
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
    border: none;
}

QLabel#MetricValue {
    font-size: 22px;
    font-weight: 700;
    background: transparent;
    border: none;
}

/* =========================================================================
   Icon-only buttons (e.g. the "?" help button)
   ========================================================================= */
QPushButton#IconButton {
    padding: 0px;
    font-size: 16px;
    font-weight: 700;
    border-radius: 16px;
}

/* =========================================================================
   Tables (Node Manager & Alert History)
   ========================================================================= */
QTableWidget {
    background-color: #131c2e;
    alternate-background-color: #0f172a;
    color: #f8fafc;
    gridline-color: transparent;
    border: 1px solid #1e293b;
    border-radius: 8px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    padding: 4px;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #1e293b;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #1e293b;
}

/* =========================================================================
   Input Fields & Search Bars
   ========================================================================= */
QLineEdit {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 8px 12px;
    color: #f8fafc;
    selection-background-color: #3b82f6;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #131c2e;
}

/* =========================================================================
   Action Buttons
   ========================================================================= */
QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #6366f1;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #4f46e5;
}

QPushButton#PrimaryButton {
    background-color: #6366f1;
    border-color: #818cf8;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background-color: #4f46e5;
}

/* =========================================================================
   Scrollbars & Text Browsers
   ========================================================================= */
QTextBrowser {
    background-color: #131c2e;
    color: #f8fafc;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 12px;
}

QScrollBar:vertical {
    background: #0b0f19;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #1e293b;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}
"""

LIGHT_GLASS_STYLE = """
/* =========================================================================
   Global Application & Window Base
   ========================================================================= */
QApplication {
    background-color: #f1f5f9;
    color: #0f172a;
    font-family: "Inter", "Noto Sans", "Cantarell", "DejaVu Sans", sans-serif;
    font-size: 13px;
}

QDialog, QWidget {
    background-color: #f1f5f9;
    color: #0f172a;
}

/* =========================================================================
   Dashboard Metric Cards (Top Summary Row)
   ========================================================================= */
QFrame#MetricCard {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-left: 3px solid #cbd5e1;
    border-radius: 10px;
}

QFrame#MetricCard[accent="blue"] {
    border-left: 3px solid #3b82f6;
}

QFrame#MetricCard[accent="green"] {
    border-left: 3px solid #16a34a;
}

QFrame#MetricCard[accent="red"] {
    border-left: 3px solid #dc2626;
}

QFrame#MetricCard[accent="purple"] {
    border-left: 3px solid #7c3aed;
}

QLabel#MetricTitle {
    color: #64748b;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.5px;
    background: transparent;
    border: none;
}

QLabel#MetricValue {
    font-size: 22px;
    font-weight: 700;
    background: transparent;
    border: none;
}

/* =========================================================================
   Icon-only buttons (e.g. the "?" help button)
   ========================================================================= */
QPushButton#IconButton {
    padding: 0px;
    font-size: 16px;
    font-weight: 700;
    border-radius: 16px;
}

/* =========================================================================
   Tables (Node Manager & Alert History)
   ========================================================================= */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    color: #0f172a;
    gridline-color: transparent;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    padding: 4px;
}

QHeaderView::section {
    background-color: #f8fafc;
    color: #475569;
    padding: 10px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
    font-weight: bold;
    font-size: 12px;
    text-transform: uppercase;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #e2e8f0;
}

/* =========================================================================
   Input Fields & Search Bars
   ========================================================================= */
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    color: #0f172a;
    selection-background-color: #3b82f6;
}

QLineEdit:focus {
    border: 1px solid #3b82f6;
    background-color: #ffffff;
}

/* =========================================================================
   Action Buttons
   ========================================================================= */
QPushButton {
    background-color: #e2e8f0;
    color: #0f172a;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #cbd5e1;
    border-color: #6366f1;
    color: #0f172a;
}

QPushButton:pressed {
    background-color: #a5b4fc;
}

QPushButton#PrimaryButton {
    background-color: #6366f1;
    border-color: #818cf8;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background-color: #4f46e5;
}

/* =========================================================================
   Scrollbars & Text Browsers
   ========================================================================= */
QTextBrowser {
    background-color: #ffffff;
    color: #0f172a;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 12px;
}

QScrollBar:vertical {
    background: #f1f5f9;
    width: 8px;
    margin: 0px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #6366f1;
}
"""
