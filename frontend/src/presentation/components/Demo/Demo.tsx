import { SettingsIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/presentation/components/Alert"
import { Avatar, AvatarFallback } from "@/presentation/components/Avatar"
import { Badge } from "@/presentation/components/Badge"
import { Button } from "@/presentation/components/Button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/presentation/components/Card"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/presentation/components/Dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/presentation/components/DropdownMenu"
import { IconButton } from "@/presentation/components/IconButton"
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/presentation/components/Popover"
import { ScrollArea } from "@/presentation/components/ScrollArea"
import { Separator } from "@/presentation/components/Separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/presentation/components/Sheet"
import { Skeleton } from "@/presentation/components/Skeleton"
import { Spinner } from "@/presentation/components/Spinner"
import { Textarea } from "@/presentation/components/Textarea"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/presentation/components/Tooltip"

import { demoCopies, type DemoProps } from "./DemoConfig"

const scrollItems = Array.from({ length: 12 }, (_, index) => index + 1)

function Demo({ textareaValue, onTextareaChange }: DemoProps) {
  return (
    <TooltipProvider>
      <main className="min-h-svh bg-background px-6 py-12 text-foreground">
        <div className="mx-auto flex w-full max-w-5xl flex-col gap-10">
          <header className="flex flex-col gap-2">
            <h1 className="font-heading text-3xl font-medium tracking-tight">
              {demoCopies.pageTitle}
            </h1>
            <p className="max-w-2xl text-muted-foreground">
              {demoCopies.pageDescription}
            </p>
          </header>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionButtons}
            </h2>
            <Card>
              <CardContent className="flex flex-wrap items-center gap-3 pt-(--card-spacing)">
                <Button>{demoCopies.primaryButton}</Button>
                <Button variant="secondary">{demoCopies.secondaryButton}</Button>
                <Button variant="outline">{demoCopies.outlineButton}</Button>
                <Button variant="ghost">{demoCopies.ghostButton}</Button>
                <Button variant="destructive">
                  {demoCopies.destructiveButton}
                </Button>
                <IconButton ariaLabel={demoCopies.iconButtonLabel}>
                  <SettingsIcon />
                </IconButton>
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionFeedback}
            </h2>
            <div className="grid gap-4 md:grid-cols-2">
              <Alert>
                <AlertTitle>{demoCopies.alertTitle}</AlertTitle>
                <AlertDescription>
                  {demoCopies.alertDescription}
                </AlertDescription>
              </Alert>
              <Alert variant="destructive">
                <AlertTitle>{demoCopies.alertDestructiveTitle}</AlertTitle>
                <AlertDescription>
                  {demoCopies.alertDestructiveDescription}
                </AlertDescription>
              </Alert>
            </div>
            <Card>
              <CardHeader>
                <CardTitle>{demoCopies.skeletonLabel}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3">
                <Skeleton className="h-4 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
                <div className="flex items-center gap-3">
                  <Spinner aria-label={demoCopies.spinnerLabel} />
                  <span className="text-sm text-muted-foreground">
                    {demoCopies.spinnerLabel}
                  </span>
                </div>
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionOverlays}
            </h2>
            <Card>
              <CardContent className="flex flex-wrap items-center gap-3 pt-(--card-spacing)">
                <Tooltip>
                  <TooltipTrigger
                    render={<Button variant="outline" />}
                  >
                    {demoCopies.tooltipTrigger}
                  </TooltipTrigger>
                  <TooltipContent>{demoCopies.tooltipContent}</TooltipContent>
                </Tooltip>

                <DropdownMenu>
                  <DropdownMenuTrigger
                    render={<Button variant="secondary" />}
                  >
                    {demoCopies.dropdownTrigger}
                  </DropdownMenuTrigger>
                  <DropdownMenuContent>
                    <DropdownMenuLabel>
                      {demoCopies.dropdownLabel}
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem>
                      {demoCopies.dropdownItemProfile}
                    </DropdownMenuItem>
                    <DropdownMenuItem>
                      {demoCopies.dropdownItemBilling}
                    </DropdownMenuItem>
                    <DropdownMenuItem variant="destructive">
                      {demoCopies.dropdownItemLogout}
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>

                <Dialog>
                  <DialogTrigger render={<Button />}>
                    {demoCopies.dialogTrigger}
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>{demoCopies.dialogTitle}</DialogTitle>
                      <DialogDescription>
                        {demoCopies.dialogDescription}
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter showCloseButton />
                  </DialogContent>
                </Dialog>

                <Sheet>
                  <SheetTrigger render={<Button variant="outline" />}>
                    {demoCopies.sheetTrigger}
                  </SheetTrigger>
                  <SheetContent>
                    <SheetHeader>
                      <SheetTitle>{demoCopies.sheetTitle}</SheetTitle>
                      <SheetDescription>
                        {demoCopies.sheetDescription}
                      </SheetDescription>
                    </SheetHeader>
                  </SheetContent>
                </Sheet>

                <Popover>
                  <PopoverTrigger render={<Button variant="ghost" />}>
                    {demoCopies.popoverTrigger}
                  </PopoverTrigger>
                  <PopoverContent>
                    <PopoverHeader>
                      <PopoverTitle>{demoCopies.popoverTitle}</PopoverTitle>
                      <PopoverDescription>
                        {demoCopies.popoverDescription}
                      </PopoverDescription>
                    </PopoverHeader>
                  </PopoverContent>
                </Popover>
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionDataDisplay}
            </h2>
            <Card>
              <CardHeader>
                <CardTitle>{demoCopies.sectionDataDisplay}</CardTitle>
                <CardDescription>
                  {demoCopies.pageDescription}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex flex-wrap items-center gap-4">
                <div className="flex flex-wrap gap-2">
                  <Badge>{demoCopies.badgeDefault}</Badge>
                  <Badge variant="secondary">
                    {demoCopies.badgeSecondary}
                  </Badge>
                  <Badge variant="outline">{demoCopies.badgeOutline}</Badge>
                  <Badge variant="destructive">
                    {demoCopies.badgeDestructive}
                  </Badge>
                </div>
                <Avatar>
                  <AvatarFallback>{demoCopies.avatarFallback}</AvatarFallback>
                </Avatar>
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionInputs}
            </h2>
            <Card>
              <CardHeader>
                <CardTitle>{demoCopies.textareaLabel}</CardTitle>
              </CardHeader>
              <CardContent>
                <Textarea
                  value={textareaValue}
                  placeholder={demoCopies.textareaPlaceholder}
                  onChange={(event) => onTextareaChange(event.target.value)}
                  aria-label={demoCopies.textareaLabel}
                />
              </CardContent>
            </Card>
          </section>

          <section className="flex flex-col gap-4">
            <h2 className="font-heading text-xl font-medium">
              {demoCopies.sectionLayout}
            </h2>
            <Card>
              <CardHeader>
                <CardTitle>{demoCopies.scrollAreaTitle}</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-4">
                <Separator aria-label={demoCopies.separatorLabel} />
                <ScrollArea className="h-40 rounded-2xl border border-border p-3">
                  <ul className="flex flex-col gap-2">
                    {scrollItems.map((item) => (
                      <li
                        key={item}
                        className="rounded-xl bg-muted px-3 py-2 text-sm"
                      >
                        {demoCopies.scrollAreaItem} {item}
                      </li>
                    ))}
                  </ul>
                </ScrollArea>
              </CardContent>
            </Card>
          </section>
        </div>
      </main>
    </TooltipProvider>
  )
}

export { Demo }
