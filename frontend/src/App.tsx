import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './auth/AuthContext'
import { RequireAuth } from './auth/RequireAuth'
import { LocaleProvider } from './i18n/LocaleContext'
import { ToastProvider } from './components/ui/ToastProvider'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/LoginPage'
import { OverviewPage } from './pages/OverviewPage'
import { AiControlRoomPage } from './pages/AiControlRoomPage'
import { SetupPage } from './pages/SetupPage'
import { InboxPage } from './pages/InboxPage'
import { CommentsPage } from './pages/CommentsPage'
import { CallsPage } from './pages/CallsPage'
import { OrdersPage } from './pages/OrdersPage'
import { PaymentsPage } from './pages/PaymentsPage'
import { DeliveryPage } from './pages/DeliveryPage'
import { SavedRepliesPage } from './pages/SavedRepliesPage'
import { ProductsPage } from './pages/ProductsPage'
import { ServicesPage } from './pages/ServicesPage'
import { InventoryPage } from './pages/InventoryPage'
import { CustomersPage } from './pages/CustomersPage'
import { ReviewsPage } from './pages/ReviewsPage'
import { LoyaltyPage } from './pages/LoyaltyPage'
import { SocialStudioPage } from './pages/SocialStudioPage'
import { AiAssistantPage } from './pages/AiAssistantPage'
import { AiTrainingPage } from './pages/AiTrainingPage'
import { CampaignsPage } from './pages/CampaignsPage'
import { FinancePage } from './pages/FinancePage'
import { DocumentsPage } from './pages/DocumentsPage'
import { AutomationsPage } from './pages/AutomationsPage'
import { TeamPage } from './pages/TeamPage'
import { IntegrationsPage } from './pages/IntegrationsPage'
import { PlanPage } from './pages/PlanPage'
import { DataHygienePage } from './pages/DataHygienePage'
import { SettingsPage } from './pages/SettingsPage'
import { SupportPage } from './pages/SupportPage'
import { SystemAdminLayout } from './pages/system-admin/SystemAdminLayout'
import { DashboardPage } from './pages/system-admin/DashboardPage'
import { UserListPage } from './pages/system-admin/UserListPage'
import { UserHistoryPage } from './pages/system-admin/UserHistoryPage'
import { PlansPage } from './pages/system-admin/PlansPage'
import { SubscribersPage } from './pages/system-admin/SubscribersPage'
import { PageVisibilityPage } from './pages/system-admin/PageVisibilityPage'
import { CostAnalysisPage } from './pages/system-admin/CostAnalysisPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <ToastProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                element={
                  <RequireAuth>
                    <AppShell />
                  </RequireAuth>
                }
              >
                <Route index element={<OverviewPage />} />
                <Route path="ai-control" element={<AiControlRoomPage />} />
                <Route path="setup" element={<SetupPage />} />
                <Route path="inbox" element={<InboxPage />} />
                <Route path="comments" element={<CommentsPage />} />
                <Route path="calls" element={<CallsPage />} />
                <Route path="orders" element={<OrdersPage />} />
                <Route path="payments" element={<PaymentsPage />} />
                <Route path="delivery" element={<DeliveryPage />} />
                <Route path="saved-replies" element={<SavedRepliesPage />} />
                <Route path="products" element={<ProductsPage />} />
                <Route path="services" element={<ServicesPage />} />
                <Route path="inventory" element={<InventoryPage />} />
                <Route path="customers" element={<CustomersPage />} />
                <Route path="reviews" element={<ReviewsPage />} />
                <Route path="loyalty" element={<LoyaltyPage />} />
                <Route path="social" element={<SocialStudioPage />} />
                <Route path="ai-assistant" element={<AiAssistantPage />} />
                <Route path="ai-training" element={<AiTrainingPage />} />
                <Route path="campaigns" element={<CampaignsPage />} />
                <Route path="finance" element={<FinancePage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="automations" element={<AutomationsPage />} />
                <Route path="team" element={<TeamPage />} />
                <Route path="integrations" element={<IntegrationsPage />} />
                <Route path="plan" element={<PlanPage />} />
                <Route path="data-hygiene" element={<DataHygienePage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="support" element={<SupportPage />} />
                <Route path="system-admin" element={<SystemAdminLayout />}>
                  <Route index element={<Navigate to="dashboard" replace />} />
                  <Route path="dashboard" element={<DashboardPage />} />
                  <Route path="users" element={<UserListPage />} />
                  <Route path="users/:shopId" element={<UserHistoryPage />} />
                  <Route path="plans" element={<PlansPage />} />
                  <Route path="subscribers" element={<SubscribersPage />} />
                  <Route path="page-visibility" element={<PageVisibilityPage />} />
                  <Route path="cost-analysis" element={<CostAnalysisPage />} />
                </Route>
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
        </ToastProvider>
      </LocaleProvider>
    </QueryClientProvider>
  )
}
