import "@testing-library/jest-dom"
import { render, screen } from "@testing-library/react"
import { DashboardPage } from "./dashboard"

test("renders dashboard", () => {
  render(<DashboardPage />)
  expect(screen.getByText("Dashboard")).toBeInTheDocument()
})
