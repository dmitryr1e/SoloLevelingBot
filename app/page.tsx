import { FinalCta, SiteFooter } from '@/components/landing/final-cta'
import { Features } from '@/components/landing/features'
import { Hero } from '@/components/landing/hero'
import { HowItWorks } from '@/components/landing/how-it-works'
import { HunterCardShowcase } from '@/components/landing/hunter-card-showcase'
import { Monarch } from '@/components/landing/monarch'
import { SiteHeader } from '@/components/landing/site-header'

export default function Page() {
  return (
    <>
      <SiteHeader />
      <main>
        <Hero />
        <Features />
        <HunterCardShowcase />
        <HowItWorks />
        <Monarch />
        <FinalCta />
      </main>
      <SiteFooter />
    </>
  )
}
